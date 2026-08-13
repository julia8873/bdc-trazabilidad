import asyncio
import os
import json
import logging
import hashlib
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

# Configuración de logging estructurado (JSON)
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if hasattr(record, "extra_info"):
            log_record.update(record.extra_info)
        return json.dumps(log_record)

logger = logging.getLogger("metrics_worker")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
if not logger.handlers:
    logger.addHandler(handler)

# Contract import
try:
    from shared_pkg.okf_contract import COMMIT_MSG_INGEST, OKF_CONTRACT_VERSION
except ImportError:
    # Para tests si shared_pkg no está instalado
    COMMIT_MSG_INGEST = "Ingesta automatica de conceptos"
    OKF_CONTRACT_VERSION = "unknown"

# Variables globales
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "1"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

class MissingCredentialsError(Exception):
    pass

class SyncEventWorker:
    def __init__(self, use_mock=None):
        self.use_mock = use_mock if use_mock is not None else os.getenv("MOCK_SERVICES", "false").lower() == "true"
        self.processed_hashes = set()
        self.semaphore = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENCY", "2")))
        
        # Log version de contrato
        logger.info(f"Iniciando metrics_worker con contrato OKF versión: {OKF_CONTRACT_VERSION}")
        
        self.check_config()

    def check_config(self):
        repo_token = os.getenv("REPO_TOKEN")
        if not self.use_mock and not repo_token:
            raise MissingCredentialsError("Fallo fail-fast: MOCK_SERVICES=false pero no se proporcionaron credenciales (REPO_TOKEN).")

    async def get_events(self):
        if self.use_mock:
            return [
                {"id": "ev1", "commit": "hash1", "msg": COMMIT_MSG_INGEST},
                {"id": "ev2", "commit": "hash2", "msg": "Otro commit"}
            ]
        # Aqui iria la logica real
        return []

    async def check_idempotency(self, commit_hash):
        # Simula query a DB
        return commit_hash in self.processed_hashes

    async def mark_as_processed(self, commit_hash):
        self.processed_hashes.add(commit_hash)

    async def mark_as_failed(self, commit_hash):
        logger.error("Evento marcado como fallido tras agotar reintentos", extra={"extra_info": {"event_hash": commit_hash, "status": "failed"}})

    @retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(multiplier=0.1, min=0.1, max=1))
    async def process_event(self, event):
        # Aqui iria el procesamiento real usando okf_contract
        if event.get("force_fail"):
            raise ValueError("Fallo simulado")
        
        logger.info("Procesando evento", extra={"extra_info": {"event": event}})
        return True

    async def handle_event_with_semaphore(self, event):
        async with self.semaphore:
            commit_hash = event["commit"]
            if await self.check_idempotency(commit_hash):
                logger.info("Evento ya procesado (idempotencia)", extra={"extra_info": {"event_hash": commit_hash}})
                return "skipped"
            
            try:
                await self.process_event(event)
                await self.mark_as_processed(commit_hash)
                logger.info("Evento procesado con éxito", extra={"extra_info": {"event_hash": commit_hash, "status": "success"}})
                return "success"
            except RetryError:
                await self.mark_as_failed(commit_hash)
                return "failed"
            except Exception as e:
                # Si es un error no recuperable o si algo pasa fuera de retry
                await self.mark_as_failed(commit_hash)
                return "failed"

    async def run_cycle(self):
        start_time = asyncio.get_event_loop().time()
        events = await self.get_events()
        
        tasks = [self.handle_event_with_semaphore(ev) for ev in events]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        duration = asyncio.get_event_loop().time() - start_time
        
        stats = {
            "total_encontrados": len(events),
            "procesados": results.count("success"),
            "skipped_idempotencia": results.count("skipped"),
            "fallidos": results.count("failed"),
            "duracion_segundos": round(duration, 3)
        }
        
        logger.info("Ciclo de polling completado", extra={"extra_info": stats})
        return stats

async def main():
    worker = SyncEventWorker()
    while True:
        await worker.run_cycle()
        await asyncio.sleep(POLL_INTERVAL_SEC)

if __name__ == "__main__":
    asyncio.run(main())
