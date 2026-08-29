import asyncio
import os
from datetime import datetime
import sys
sys.path.append("/app")
from metrics_api.main import _trigger_reconciliation_for_student
from metrics_api.database import SessionLocal
from metrics_api.models import DiscrepanciaAuditoria, EventoSync, Interaccion
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

async def test():
    engine = create_engine(os.environ["DATABASE_URL"])
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    db.query(DiscrepanciaAuditoria).delete()
    db.query(EventoSync).filter_by(commit_sha="fake-sha-test").delete()
    db.query(Interaccion).filter_by(referencia_evento="fake-sha-test").delete()
    db.commit()
    
    d = DiscrepanciaAuditoria(
        moodle_user_id=3,
        moodle_course_id=2,
        commit_sha="fake-sha-test",
        tipo_discrepancia="COMMIT_ORPHAN",
        detalles={"fake": "data"},
        resuelta=0
    )
    db.add(d)
    db.commit()
    
    print("\n--- TEST 2: EXITO EN MAPEO-API ---")
    os.environ["MAPEO_API_URL"] = "http://localhost:9999/fake"
    
    import httpx
    
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        async def get(self, url, headers=None, timeout=None):
            class R:
                status_code = 200
                headers = {}
                def json(self): return [{"sha": "fake-sha-test", "commit": {"message": "INGEST: Test commit", "author": {"date": datetime.utcnow().isoformat()}}}]
            return R()
        async def post(self, url, json=None, headers=None, timeout=None):
            print("MOCK POST CALLED!")
            class R:
                status_code = 201
                def json(self): return {"status": "ok", "commit_log_ref": "fake-sha-from-mapeo-api-log"}
            return R()
    
    # Overwrite the global module attribute
    httpx.AsyncClient = MockClient
    sys.modules["httpx"].AsyncClient = MockClient
    
    res = await _trigger_reconciliation_for_student(
        {"moodle_user_id": 3, "moodle_course_id": 2, "repo_url": "https://github.com/test-org/test-repo"},
        db,
        1
    )
    print(res)
        
    db.expire_all()
    d_after = db.query(DiscrepanciaAuditoria).filter_by(commit_sha="fake-sha-test").first()
    print(f"Despues del exito (mapeo-api respondio HTTP 201):")
    if d_after:
        print(f"  resuelta = {d_after.resuelta}")
        print(f"  resuelta_at = {d_after.resuelta_at}")
        print(f"  resuelta_por = {d_after.resuelta_por}")
        print(f"  commit_log_ref = {d_after.commit_log_ref}")
    else:
        print("  d_after IS NONE")

if __name__ == "__main__":
    asyncio.run(test())
