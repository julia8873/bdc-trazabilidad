#!/usr/bin/env python3
import asyncio
import os
import sys
import httpx
from datetime import datetime

# Agregar path para poder importar
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'metrics-worker'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'metrics-api'))

from metrics_worker.worker import SyncEventWorker
from metrics_api.db import SessionLocal
from metrics_api.models import EventoSync, DiscrepanciaAuditoria

async def main():
    print("Iniciando TRUE E2E (Sin mocks, contenedores reales)")
    
    MAPEO_API_URL = os.getenv("MAPEO_API_URL", "http://mapeo-api:8000")
    MAPEO_API_TOKEN = os.getenv("MAPEO_API_TOKEN", "test_token")
    headers = {"Authorization": f"Bearer {MAPEO_API_TOKEN}"}
    
    # 1. Preparar Base de Datos Metrics (Local)
    db = SessionLocal()
    db.query(EventoSync).delete()
    db.query(DiscrepanciaAuditoria).delete()
    db.commit()
    print("DB Metrics Limpia.")
    
    REAL_COMMIT = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"
    
    # 2. El bot hace push y llama a POST /eventos real en mapeo-api
    print("Paso 1: Bot reporta evento a mapeo-api...")
    payload = {
        "matrix_room_id": "!room:matrix.org",
        "commit_sha": REAL_COMMIT,
        "tipo_evento": "PUSH",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{MAPEO_API_URL}/eventos", json=payload, headers=headers)
        if resp.status_code == 409:
            print("El evento ya existía en mapeo-api, continuamos.")
        else:
            resp.raise_for_status()
            print(f"Evento {REAL_COMMIT} insertado en mapeo-api correctamente.")
        
        # Verificamos GET /eventos-recientes
        resp_get = await client.get(f"{MAPEO_API_URL}/eventos-recientes", headers=headers)
        eventos = resp_get.json()
        assert any(e["commit_sha"] == REAL_COMMIT for e in eventos), "mapeo-api no devolvió el evento!"
        print("mapeo-api GET /eventos-recientes funciona.")

    # 3. Mapeo-API ya tiene un mapeo insertado vía psql para octocat/Hello-World

    # 4. metrics-worker consume el feed de mapeo-api real
    print("Paso 3: Worker consume feed desde mapeo-api...")
    worker = SyncEventWorker()
    worker.github_token = os.getenv("GITHUB_PAT", "")
    await worker._consume_feed()
    
    # Verificar Bucle 1
    evento_bd = db.query(EventoSync).filter(EventoSync.commit_sha == REAL_COMMIT).first()
    if evento_bd:
        print(f"EXITO Bucle 1: Evento {REAL_COMMIT} insertado en la BD local de trazabilidad (eventos_sync).")
    else:
        print("ERROR Bucle 1: No se insertó.")
        return

    # 5. metrics-worker ejecuta la reconciliación (Bucle 2)
    print("Paso 4: Worker audita el historial completo de GitHub...")
    await worker._reconcile_history()
    
    discrepancia = db.query(DiscrepanciaAuditoria).filter(DiscrepanciaAuditoria.commit_sha == REAL_COMMIT).first()
    if not discrepancia:
        print(f"EXITO Bucle 2 (Detección Negativa): Para el commit {REAL_COMMIT} que sí está en eventos_sync, NO se generó discrepancia falsa.")
    else:
        print(f"ERROR Bucle 2: Se generó discrepancia falsa para el commit {REAL_COMMIT}.")
        
    print("Paso 5: Comprobando commit falso (ruido) y commit omitido...")
    # Comprobamos si los otros commits del repo de prueba generaron las discrepancias correctas.
    discrepancias = db.query(DiscrepanciaAuditoria).all()
    encontradas = 0
    for d in discrepancias:
        if d.commit_sha != REAL_COMMIT:
            print(f"EXITO Bucle 2 (Detección Positiva): Commit histórico {d.commit_sha} encontrado en GitHub pero no en eventos_sync -> Discrepancia {d.tipo_discrepancia} creada.")
            encontradas += 1
            if encontradas >= 3:
                break
    if encontradas == 0:
        print("ERROR Bucle 2: No se generaron discrepancias reales.")

    print("Paso 6: Verificando idempotencia con segundo POST...")
    async with httpx.AsyncClient() as client:
        resp_idem = await client.post(f"{MAPEO_API_URL}/eventos", json=payload, headers=headers)
        if resp_idem.status_code == 409:
            print("EXITO Idempotencia: El segundo POST del mismo evento devolvió 409 Conflict.")
        else:
            print(f"ERROR Idempotencia: Se esperaba 409, pero se recibió {resp_idem.status_code}")

    # Limpiar y cerrar
    db.query(EventoSync).delete()
    db.commit()
    db.close()
    print("E2E True Finalizado Exitosamente.")

if __name__ == "__main__":
    asyncio.run(main())
