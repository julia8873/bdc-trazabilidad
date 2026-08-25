import httpx
import asyncio
import os
import re
import logging
from typing import Dict, Any, List
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from metrics_api.db import SessionLocal
from metrics_api.models import EventoSync, DiscrepanciaAuditoria, Interaccion
from shared_pkg.okf_contract import COMMIT_MSG_INGEST, COMMIT_MSG_REVERT, COMMIT_MSG_SYNC, COMMIT_MSG_LOG, COMMIT_MSG_CONCEPTOS

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("metrics_worker")

# Cargar configuracion: primero busca en config/config.yaml compartido (Fase 9),
# con fallback al config.yaml local del worker y a variables de entorno.
def _load_config():
    # Ruta compartida: bdc-trazabilidad/config/config.yaml
    shared_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "config.yaml")
    # Ruta local del worker
    local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    for path in (shared_path, local_path):
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
                if data:
                    return data
        except Exception:
            continue
    return {}

_config_yaml = _load_config()
_timings = _config_yaml.get("timings", {})
# Compatibilidad con la clave legacy del worker local
_worker_intervals = _config_yaml.get("worker", {}).get("intervals", {})

POLL_INTERVAL_SEC = (
    _timings.get("poll_interval_sec")
    or _worker_intervals.get("poll_sec")
    or int(os.getenv("POLL_INTERVAL_SEC", "15"))
)
RECONCILIATION_INTERVAL_SEC = (
    _timings.get("reconciliation_interval_sec")
    or _worker_intervals.get("reconciliation_sec")
    or int(os.getenv("RECONCILIATION_INTERVAL_SEC", "86400"))
)
logger.info(f"Timings cargados: poll={POLL_INTERVAL_SEC}s, reconciliation={RECONCILIATION_INTERVAL_SEC}s")

MAPEO_API_URL = os.getenv("MAPEO_API_URL", "http://mapeo-api:8000")
MAPEO_API_TOKEN = os.getenv("MAPEO_API_TOKEN", "")

class MissingCredentialsError(Exception):
    pass

class SyncEventWorker:
    """
    Clase principal que implementa el worker de sincronizacion de eventos de GitHub.
    """
    def __init__(self, use_mock=None):
        self.use_mock = use_mock if use_mock is not None else os.getenv("MOCK_SERVICES", "false").lower() == "true"
        self.semaphore = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENCY", "2")))
        logger.info("Iniciando metrics_worker con dos bucles independientes.")
        self.check_config()

    def check_config(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        if not self.use_mock and not self.github_token:
            raise MissingCredentialsError("Fallo fail-fast: MOCK_SERVICES=false pero no se proporcionó GITHUB_TOKEN.")

    # ---------------------------------------------------------
    # BUCLE 1: CONSUMIDOR DE FEED (Alta frecuencia)
    # ---------------------------------------------------------
    async def run_feed_consumer(self):
        while True:
            try:
                await self._consume_feed()
            except Exception as e:
                logger.error(f"Error en feed consumer: {e}")
            await asyncio.sleep(POLL_INTERVAL_SEC)

    async def _consume_feed(self):
        headers = {"Authorization": f"Bearer {MAPEO_API_TOKEN}"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{MAPEO_API_URL}/v1/eventos-recientes", headers=headers, timeout=10)
                resp.raise_for_status()
                events = resp.json()
                
                resp2 = await client.get(f"{MAPEO_API_URL}/v1/mapeos", headers=headers, timeout=10)
                resp2.raise_for_status()
                mapeos = resp2.json()
                mapeo_dict = {m.get("matrix_room_id"): m for m in mapeos if m.get("matrix_room_id")}
        except Exception as e:
            logger.error(f"Error fetching events from mapeo-api: {e}")
            return

        if not events:
            return

        db = SessionLocal()
        try:
            procesados = 0
            for event in events:
                commit_sha = event.get("commit_sha")
                if not commit_sha:
                    continue
                
                existe = db.query(EventoSync).filter(EventoSync.commit_sha == commit_sha).first()
                if not existe:
                    m = mapeo_dict.get(event.get("matrix_room_id"), {})
                    moodle_user_id = m.get("moodle_user_id")
                    moodle_course_id = m.get("moodle_course_id")
                    
                    if not moodle_user_id or not moodle_course_id:
                        logger.warning(f"Omitiendo evento {commit_sha} por falta de mapeo.")
                        continue
                        
                    db_event = EventoSync(
                        moodle_user_id=moodle_user_id,
                        moodle_course_id=moodle_course_id,
                        commit_sha=commit_sha,
                        tipo_evento=event.get("tipo_evento", "PUSH"),
                        estado="SUCCESS",
                        resultado={"verified_via_feed": True}
                    )
                    db.add(db_event)
                    
                    if event.get("tipo_evento") in ["INTERACTION", "INGEST"]:
                        from datetime import datetime
                        try:
                            # event["timestamp"] comes as "YYYY-MM-DDTHH:MM:SSZ"
                            ts_str = event.get("timestamp", "").replace("Z", "+00:00")
                            ts = datetime.fromisoformat(ts_str).replace(tzinfo=None)
                        except Exception:
                            ts = datetime.utcnow()
                            
                        tipo = "chat" if event.get("tipo_evento") == "INTERACTION" else "file_upload"
                            
                        db_int = Interaccion(
                            moodle_user_id=moodle_user_id,
                            moodle_course_id=moodle_course_id,
                            tipo_interaccion=tipo,
                            referencia_evento=commit_sha,
                            timestamp=ts
                        )
                        db.add(db_int)
                        
                    procesados += 1
            if procesados > 0:
                db.commit()
                logger.info(f"Feed consumer: {procesados} eventos nuevos registrados.")
        except Exception as e:
            db.rollback()
            logger.error(f"Error insertando eventos del feed: {e}")
        finally:
            db.close()

    # ---------------------------------------------------------
    # BUCLE 2: AUDITOR DE GITHUB (Baja frecuencia)
    # ---------------------------------------------------------
    async def run_reconciliation(self):
        while True:
            try:
                await self._reconcile_history()
            except Exception as e:
                logger.error(f"Error en reconciliacion: {e}")
            await asyncio.sleep(RECONCILIATION_INTERVAL_SEC)

    async def _get_all_commits(self, owner: str, repo: str, since: str = None) -> List[Dict[str, Any]]:
        commits = []
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        if since:
            url += f"?since={since}"
            
        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
        
        async with httpx.AsyncClient() as client:
            while url:
                if self.use_mock:
                    if 'page=' not in url:
                        commits.extend([{"sha": "mock_commit_1"}, {"sha": "mock_commit_2"}])
                    break
                    
                resp = await client.get(url, headers=headers, timeout=10)
                if resp.status_code == 404:
                    logger.warning(f"Repo {owner}/{repo} no encontrado.")
                    break
                elif resp.status_code == 429 or "rate limit" in resp.text.lower() or resp.status_code == 403:
                    logger.warning("Rate limit alcanzado, backoff...")
                    await asyncio.sleep(2)
                    continue
                resp.raise_for_status()
                
                page_commits = resp.json()
                if not page_commits:
                    break
                commits.extend(page_commits)
                
                link_header = resp.headers.get("Link", "")
                url = None
                if link_header:
                    links = link_header.split(",")
                    for link in links:
                        if 'rel="next"' in link:
                            url = link[link.find("<")+1:link.find(">")]
                            break
        return commits

    async def _reconcile_history(self):
        logger.info("Iniciando auditoria completa de reconciliacion.")
        headers = {"Authorization": f"Bearer {MAPEO_API_TOKEN}"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{MAPEO_API_URL}/v1/mapeos", headers=headers, timeout=10)
                resp.raise_for_status()
                mapeos = resp.json()
        except Exception as e:
            logger.error(f"Auditoria: Error fetching mapeos: {e}")
            return

        db = SessionLocal()
        from metrics_api.models import AuditoriaEstado
        from datetime import datetime
        try:
            for mapeo in mapeos:
                if mapeo.get("estado") != "ACTIVO":
                    continue
                repo_url = mapeo.get("repo_url")
                if not repo_url:
                    continue
                    
                match = re.search(r"github\.com/([^/]+)/([^/.]+)", repo_url)
                if not match:
                    continue
                owner, repo = match.groups()
                m_user_id = mapeo.get("moodle_user_id")
                m_course_id = mapeo.get("moodle_course_id")
                
                # Retrieve last audited state
                estado = db.query(AuditoriaEstado).filter(
                    AuditoriaEstado.moodle_user_id == m_user_id,
                    AuditoriaEstado.moodle_course_id == m_course_id
                ).first()
                
                since_str = None
                if estado and estado.last_audited_timestamp:
                    since_str = estado.last_audited_timestamp.isoformat() + "Z"
                
                commits = await self._get_all_commits(owner, repo, since=since_str)
                print(f"DEBUG: Found {len(commits)} commits for {owner}/{repo} since {since_str}")
                
                max_commit_date = estado.last_audited_timestamp if estado else None
                
                for commit in commits:
                    sha = commit.get("sha")
                    if not sha:
                        continue
                        
                    commit_date_str = commit.get("commit", {}).get("author", {}).get("date")
                    if commit_date_str:
                        try:
                            # Parse ISO 8601 string to naive datetime for DB
                            c_date = datetime.fromisoformat(commit_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                            if not max_commit_date or c_date > max_commit_date:
                                max_commit_date = c_date
                        except Exception:
                            pass
                    
                    commit_msg = commit.get("commit", {}).get("message", "")
                    if not (commit_msg.startswith(COMMIT_MSG_INGEST) or 
                            commit_msg.startswith(COMMIT_MSG_REVERT) or 
                            commit_msg.startswith(COMMIT_MSG_SYNC) or
                            commit_msg.startswith(COMMIT_MSG_LOG) or
                            commit_msg.startswith(COMMIT_MSG_CONCEPTOS)):
                        continue
                    
                    existe_sync = db.query(EventoSync).filter(EventoSync.commit_sha == sha).first()
                    existe_disc = db.query(DiscrepanciaAuditoria).filter(DiscrepanciaAuditoria.commit_sha == sha).first()
                    
                    if not existe_sync and not existe_disc:
                        logger.warning(f"Auditoria: Discrepancia detectada (Missing) para commit {sha}")
                        db_disc = DiscrepanciaAuditoria(
                            moodle_user_id=m_user_id,
                            moodle_course_id=m_course_id,
                            commit_sha=sha,
                            tipo_discrepancia="EVENTO_MISSING_IN_FEED",
                            detalles={"owner": owner, "repo": repo}
                        )
                        db.add(db_disc)
                
                if max_commit_date:
                    if not estado:
                        estado = AuditoriaEstado(
                            moodle_user_id=m_user_id,
                            moodle_course_id=m_course_id,
                            repo_owner=owner,
                            repo_name=repo,
                            last_audited_timestamp=max_commit_date
                        )
                        db.add(estado)
                    else:
                        estado.last_audited_timestamp = max_commit_date
                        
            db.commit()
            logger.info("Auditoria completa finalizada.")
        except Exception as e:
            db.rollback()
            logger.error(f"Auditoria error: {e}")
        finally:
            db.close()

async def main():
    worker = SyncEventWorker()
    await asyncio.gather(
        worker.run_feed_consumer(),
        worker.run_reconciliation()
    )

if __name__ == "__main__":
    asyncio.run(main())
