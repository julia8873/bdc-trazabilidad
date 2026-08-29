import os
import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configuramos la DB apuntando al host (o a postgres en docker)
# Si lo corremos dentro de docker: postgresql://metrics_user:metrics_pass@postgres:5432/mapeo_db
DB_URL = os.getenv("DATABASE_URL", "postgresql://metrics_user:metrics_pass@postgres:5432/mapeo_db")

engine = create_engine(DB_URL, connect_args={"options": "-csearch_path=metrics"})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_flujo_e2e_discrepancia(mocker):
    """
    Test End-to-End que inserta una discrepancia en BD, llama a _trigger_reconciliation_for_student
    y verifica que se actualizan las columnas correctamente, simulando la llamada al mapeo-api.
    """
    from metrics_api.models import DiscrepanciaAuditoria, EventoSync
    from metrics_api.main import _trigger_reconciliation_for_student
    import asyncio

    session = SessionLocal()
    try:
        # 1. Crear una discrepancia pendiente en BD
        # Primero limpiar para este user/curso (1001, 1001)
        session.query(DiscrepanciaAuditoria).filter_by(moodle_user_id=1001, moodle_course_id=1001).delete()
        session.query(EventoSync).filter_by(moodle_user_id=1001, moodle_course_id=1001).delete()
        session.commit()

        d = DiscrepanciaAuditoria(
            moodle_user_id=1001,
            moodle_course_id=1001,
            commit_sha="dummy_sha_123",
            tipo_discrepancia="LOG_DELETED",
            detalles={"razon": "test"},
            timestamp=datetime.datetime.utcnow(),
            resuelta=0
        )
        session.add(d)
        session.commit()

        # 2. Mockear httpx.AsyncClient para github y mapeo-api
        from unittest.mock import MagicMock
        mock_get = mocker.AsyncMock()
        mock_post = mocker.AsyncMock()

        # GitHub get devuelve 1 commit con prefijo LOG: para q el script lo procese y resuelva la discrepancia
        mock_get.return_value.status_code = 200
        mock_get.return_value.json = MagicMock(return_value=[
            {"sha": "dummy_sha_123", "commit": {"message": "LOG: testing", "author": {"date": "2023-01-01T00:00:00Z"}}}
        ])
        mock_get.return_value.headers = {}

        # Mapeo API post devuelve 201 y un commit_log_ref
        mock_post.return_value.status_code = 201
        mock_post.return_value.json = MagicMock(return_value={"commit_log_ref": "http://github.com/test/commit/abc"})

        class DummyClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
            async def get(self, url, headers=None, timeout=None):
                return await mock_get(url, headers=headers, timeout=timeout)
            async def post(self, url, json=None, headers=None, timeout=None):
                return await mock_post(url, json=json, headers=headers, timeout=timeout)

        mocker.patch("httpx.AsyncClient", return_value=DummyClient())

        mapeo = {
            "repo_url": "https://github.com/user/repo",
            "moodle_user_id": 1001,
            "moodle_course_id": 1001
        }

        # 3. Llamar al sync asíncrono
        asyncio.run(_trigger_reconciliation_for_student(mapeo, session, current_user_id=99))

        # 4. Verificar en BD que se actualizó
        session.refresh(d)
        assert d.resuelta == 1, "La discrepancia no fue marcada como resuelta!"
        assert d.resuelta_por == 99, "No se guardó el usuario que resolvió!"
        assert d.resuelta_at is not None, "No se guardó la fecha de resolución!"
        assert d.commit_log_ref == "http://github.com/test/commit/abc", "No se guardó la referencia al commit de github!"
        
        print("PRUEBA E2E DISCREPANCIA COMPLETADA CON ÉXITO Y BD ACTUALIZADA")
    finally:
        session.close()
