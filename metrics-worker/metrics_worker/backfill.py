#!/usr/bin/env python3
"""
Script de Backfill (Run-once)
Lee los ficheros `.jsonl` del directorio de repositorios del bot
y emite de nuevo los eventos a `mapeo-api` si faltaron.
Cubre la resiliencia en caso de que MapeoClient falle tras varios reintentos.
"""

import os
import glob
import json
import httpx
import asyncio

MAPEO_API_URL = os.getenv("MAPEO_API_URL", "http://localhost:8000")
MAPEO_API_TOKEN = os.getenv("MAPEO_API_TOKEN", "")

async def backfill():
    if not MAPEO_API_TOKEN:
        print("Falta MAPEO_API_TOKEN en el entorno.")
        return

    repos_dir = "/tmp/llm_wiki_repos"
    
    # Buscar todos los JSONL de backfill que sirven como buffer de seguridad
    jsonl_files = glob.glob(f"{repos_dir}/**/.backfill.jsonl", recursive=True)
    if not jsonl_files:
        print("No se encontraron ficheros JSONL en el buffer local.")
        return
        
    headers = {"Authorization": f"Bearer {MAPEO_API_TOKEN}"}
    
    async with httpx.AsyncClient() as client:
        for file_path in jsonl_files:
            print(f"Procesando buffer de durabilidad: {file_path}")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                            
                        data = json.loads(line)
                        commit_sha = data.get("commit_sha")
                        matrix_room_id = data.get("matrix_room_id")
                        
                        if not commit_sha or not matrix_room_id:
                            print("Registro inválido (sin commit_sha o matrix_room_id), omitiendo.")
                            continue
                        
                        import datetime
                        evento_payload = {
                            "matrix_room_id": matrix_room_id,
                            "commit_sha": commit_sha,
                            "tipo_evento": "BACKFILL",
                            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                        }
                        
                        resp = await client.post(
                            f"{MAPEO_API_URL}/v1/eventos",
                            json=evento_payload,
                            headers=headers,
                            timeout=5
                        )
                        if resp.status_code in (200, 201):
                            print(f"Backfill OK para evento {commit_sha[:8]}")
                        elif resp.status_code == 409:
                            print(f"Backfill ignorado para {commit_sha[:8]}: Ya existía en mapeo-api (Idempotente)")
                        else:
                            print(f"Backfill falló para {commit_sha[:8]}: {resp.status_code}")
                            
            except Exception as e:
                print(f"Error parseando {file_path}: {e}")

if __name__ == "__main__":
    asyncio.run(backfill())
