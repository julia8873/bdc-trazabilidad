import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from metrics_api.models import Interaccion
from metrics_api.main import get_all_jsonls_from_dir
import os
import sys
from datetime import datetime

engine = create_engine(os.getenv("DATABASE_URL", "postgresql://metrics_user:metrics_pass@postgres:5432/mapeo_db"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def main():
    session = SessionLocal()
    ref = "311a1b7ada3283fd6a49627ffaa0f7e4220f844d"
    interaccion = session.query(Interaccion).filter(Interaccion.referencia_evento == ref).first()
    
    repo_url = "https://github.com/julia8873/EDII-alumno1"
    os.environ["GITHUB_TOKEN_AGENT"] = os.environ.get("GITHUB_TOKEN_AGENT", "")
    
    data_logs = await get_all_jsonls_from_dir(repo_url, "logs/interacciones")
    for d in data_logs:
        ts_str = d.get("timestamp", "")
        if ts_str:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
            diff = abs((ts - interaccion.timestamp).total_seconds()) if interaccion else -1
            if diff >= 0 and diff <= 60:
                print("MATCH FOUND IN logs/interacciones!")

    data_okf = await get_all_jsonls_from_dir(repo_url, "okf/interacciones")
    for d in data_okf:
        ts_str = d.get("timestamp", "")
        if ts_str:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
            diff = abs((ts - interaccion.timestamp).total_seconds()) if interaccion else -1
            if diff >= 0 and diff <= 60:
                print("MATCH FOUND IN okf/interacciones!")

asyncio.run(main())
