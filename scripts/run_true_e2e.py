#!/usr/bin/env python3
import asyncio
import os
import sys
import httpx
from datetime import datetime
import psycopg2
import uuid

# Agregar path para poder importar
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'metrics-worker'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'metrics-api'))

from metrics_worker.worker import SyncEventWorker
from metrics_api.db import SessionLocal
from metrics_api.models import EventoSync, DiscrepanciaAuditoria

async def main():
    print("Iniciando TRUE E2E (Fase 8 - Flujo Completo con Push Real)")
    
    MAPEO_API_URL = os.getenv("MAPEO_API_URL", "http://mapeo-api:8000")
    MAPEO_API_TOKEN = os.getenv("MAPEO_API_TOKEN", "8f3b2a9d8f3b2a9d8f3b2a9d8f3b2a9d")
    headers_mapeo = {"Authorization": f"Bearer {MAPEO_API_TOKEN}"}
    
    # 1. Preparar Base de Datos Metrics (Local)
    db = SessionLocal()
    db.query(EventoSync).delete()
    db.query(DiscrepanciaAuditoria).delete()
    db.commit()
    
    e2e_fork_url = os.getenv("E2E_TEST_FORK_URL", "https://github.com/julia8873/e2e-test-repo.git")
    
    # Prepara Base de Datos mapeo_db (Mapeos)
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://mapeo_user:mapeo_db_pass@postgres:5432/mapeo_db"))
        cur = conn.cursor()
        cur.execute("DELETE FROM eventos_bot;")
        cur.execute("DELETE FROM mapeos;")
        conn.commit()
        
        # Uso parametrizado del fork
        cur.execute("INSERT INTO mapeos (moodle_user_id, moodle_course_id, repo_url, matrix_room_id, git_provider, estado, created_at, updated_at) VALUES (999, 999, %s, '!room:matrix.org', 'github', 'ACTIVO', NOW(), NOW());", (e2e_fork_url,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("Error PostgreSQL setup:", e)
    
    print("DB Metrics y Mapeo Limpias.")
    
    print("-> Clonando y generando un nuevo commit real en GitHub...")
    import subprocess
    GITHUB_PAT = os.getenv("GITHUB_PAT")
    
    # Extraer repo basename y usuario del URL
    import re
    match = re.match(r"https://github\.com/(.+?)/(.+?)\.git", e2e_fork_url)
    if match:
        user, repo = match.groups()
        repo_url = f"https://{GITHUB_PAT}@github.com/{user}/{repo}.git"
    else:
        # Fallback si el regex no machea
        repo_url = f"https://{GITHUB_PAT}@github.com/julia8873/e2e-test-repo.git"
    
    subprocess.run(f"git clone {repo_url} /tmp/e2e-test-repo", shell=True, check=True)
    subprocess.run("git config user.name 'E2E Bot' && git config user.email 'e2e@example.com'", shell=True, cwd="/tmp/e2e-test-repo", check=True)
    
    fake_file = f"/tmp/e2e-test-repo/e2e_{uuid.uuid4().hex[:8]}.txt"
    with open(fake_file, "w") as f:
        f.write("e2e test")
        
    subprocess.run(f"git add . && git commit -m 'E2E test commit' && git push", shell=True, cwd="/tmp/e2e-test-repo", check=True)
    
    REAL_COMMIT = subprocess.check_output("git rev-parse HEAD", shell=True, cwd="/tmp/e2e-test-repo").decode().strip()
    print(f"-> Commit generado exitosamente: {REAL_COMMIT}")
    
    print("Paso 1: Bot reporta evento a mapeo-api...")
    payload = {
        "matrix_room_id": "!room:matrix.org",
        "commit_sha": REAL_COMMIT,
        "tipo_evento": "PUSH",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{MAPEO_API_URL}/eventos", json=payload, headers=headers_mapeo)
        resp.raise_for_status()
        print(f"Evento {REAL_COMMIT} insertado en mapeo-api correctamente.")
        
        resp_get = await client.get(f"{MAPEO_API_URL}/eventos-recientes", headers=headers_mapeo)
        eventos = resp_get.json()
        assert any(e["commit_sha"] == REAL_COMMIT for e in eventos), "mapeo-api no devolvió el evento!"
        print("mapeo-api GET /eventos-recientes funciona.")

    print("Paso 3: Worker consume feed desde mapeo-api...")
    worker = SyncEventWorker(use_mock=False)
    worker.github_token = os.getenv("GITHUB_PAT", "")
    await worker._consume_feed()
    
    evento_bd = db.query(EventoSync).filter(EventoSync.commit_sha == REAL_COMMIT).first()
    if evento_bd:
        print(f"EXITO Bucle 1: Evento {REAL_COMMIT} insertado en la BD local de trazabilidad (eventos_sync).")
    else:
        print("ERROR Bucle 1: No se insertó.")
        sys.exit(1)

    print("Paso 4: Worker audita el historial completo de GitHub...")
    await worker._reconcile_history()
    
    discrepancia = db.query(DiscrepanciaAuditoria).filter(DiscrepanciaAuditoria.commit_sha == REAL_COMMIT).first()
    if not discrepancia:
        print(f"EXITO Bucle 2 (Detección Negativa): Para el commit {REAL_COMMIT} que sí está en eventos_sync, NO se generó discrepancia falsa.")
    else:
        print(f"ERROR Bucle 2: Se generó discrepancia falsa para el commit {REAL_COMMIT}.")
        sys.exit(1)
        
    print("Paso 6: Verificando idempotencia con segundo POST...")
    async with httpx.AsyncClient() as client:
        resp_idem = await client.post(f"{MAPEO_API_URL}/eventos", json=payload, headers=headers_mapeo)
        if resp_idem.status_code == 409:
            print("EXITO Idempotencia: El segundo POST devolvió 409 Conflict.")
        else:
            print(f"ERROR Idempotencia: Se esperaba 409, pero se recibió {resp_idem.status_code}")
            sys.exit(1)

    db.query(EventoSync).delete()
    db.commit()
    db.close()
    print("E2E True Finalizado Exitosamente.")

if __name__ == "__main__":
    asyncio.run(main())
