#!/usr/bin/env python3
import asyncio
import os
import sys
import httpx

# Agregar path para poder importar
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'metrics-worker'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'metrics-api'))

from metrics_worker.worker import SyncEventWorker
from metrics_api.db import SessionLocal
from metrics_api.models import EventoSync, DiscrepanciaAuditoria
from unittest.mock import patch, AsyncMock

async def main():
    print("Iniciando test E2E (No Simulado sobre la API de GitHub)")
    
    # 1. Preparar Base de Datos Real
    db = SessionLocal()
    db.query(EventoSync).delete()
    db.query(DiscrepanciaAuditoria).delete()
    db.commit()
    print("DB Limpia.")
    
    # El commit real que vamos a probar
    REAL_OWNER = "octocat"
    REAL_REPO = "Hello-World"
    REAL_COMMIT = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"
    
    worker = SyncEventWorker(use_mock=False)
    # Ignoramos token para usar acceso público (rate limit de 60 req/h sirve para 1 test)
    worker.github_token = ""
    
    # Mockear mapeo-api para que devuelva nuestro evento y nuestro mapeo real
    print(f"Paso 1: Mapeo-API reporta evento con commit_sha={REAL_COMMIT}")
    original_get = httpx.AsyncClient.get
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # 2. Bucle 1 consume el evento
        from unittest.mock import MagicMock
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"commit_sha": REAL_COMMIT, "moodle_user_id": 99, "moodle_course_id": 99, "tipo_evento": "PUSH"}
        ]
        mock_get.return_value = mock_resp
        await worker._consume_feed()
        
    # Verificar Bucle 1
    evento_bd = db.query(EventoSync).filter(EventoSync.commit_sha == REAL_COMMIT).first()
    if evento_bd:
        print(f"EXITO Bucle 1: Evento {REAL_COMMIT} insertado en eventos_sync.")
    else:
        print("ERROR Bucle 1: No se insertó.")
        return

    print("Paso 2: Bucle 2 audita historial completo de GitHub...")
    original_get = httpx.AsyncClient.get
    async def custom_get(self, url, *args, **kwargs):
        if "mapeos" in str(url):
            from unittest.mock import MagicMock
            m = MagicMock()
            m.status_code = 200
            m.json.return_value = [{"github_fork_url": f"https://github.com/{REAL_OWNER}/{REAL_REPO}.git", "moodle_user_id": 99, "moodle_course_id": 99}]
            return m
        
        try:
            resp = await original_get(self, url, *args, **kwargs)
            return resp
        except Exception as e:
            raise
        
    httpx.AsyncClient.get = custom_get
    try:
        await worker._reconcile_history()
    finally:
        httpx.AsyncClient.get = original_get
    
    # Verificar Bucle 2
    discrepancia = db.query(DiscrepanciaAuditoria).filter(DiscrepanciaAuditoria.commit_sha == REAL_COMMIT).first()
    if not discrepancia:
        print(f"EXITO Bucle 2: Commit {REAL_COMMIT} encontrado en el historial de GitHub de {REAL_OWNER}/{REAL_REPO}. NO se generó discrepancia falsa.")
    else:
        print("ERROR Bucle 2: Se generó discrepancia falsa.")
        
    # Comprobar qué pasa con un commit FALSO
    FAKE_COMMIT = "0000000000000000000000000000000000000000"
    print(f"Paso 3: Simulando fallo silencioso con commit que no está en el feed")
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
        
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
