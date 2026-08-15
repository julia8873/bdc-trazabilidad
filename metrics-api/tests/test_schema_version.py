"""
Test de versión de esquema.

Verifica que get_schema_version() devuelve un valor coherente (no None)
tras aplicar las migraciones con `alembic upgrade head`.
"""
import pytest
from metrics_api.db import get_session
from metrics_api.repository import get_schema_version


def test_schema_version_is_set():
    """
    Tras upgrade head, alembic_version debe tener exactamente una fila
    con una revisión no vacía.
    """
    session = next(get_session())
    try:
        version = get_schema_version(session)
        assert version is not None, (
            "get_schema_version() devolvió None — "
            "probablemente alembic upgrade head no se ha ejecutado aún."
        )
        assert isinstance(version, str)
        assert len(version) > 0
    finally:
        session.close()

def test_health_endpoint(client):
    """
    Verifica que el endpoint /health devuelve status ok y la versión del esquema.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "schema_version" in data
    assert data["schema_version"] is not None
