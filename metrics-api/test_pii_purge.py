"""
Test de purga por retención del PiiVault.
Verifica que la lógica de purga de apscheduler (extraída como función pura)
elimina registros con expires_at en el pasado y conserva los vigentes.

Ejecutar con: docker compose exec metrics-api pytest test_pii_purge.py -v
"""
import datetime
import uuid
import pytest

from metrics_api.db import SessionLocal
from metrics_api.models import PiiVault
from sqlalchemy import delete


def _purge_expired(db) -> int:
    """Misma lógica que purge_expired_pii() en main.py lifespan."""
    result = db.execute(
        delete(PiiVault).where(PiiVault.expires_at < datetime.datetime.utcnow())
    )
    db.commit()
    return result.rowcount


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_purga_elimina_expirados_y_conserva_vigentes(db):
    """
    1. Insertar una fila expirada (expires_at en el pasado).
    2. Insertar una fila vigente (expires_at en el futuro).
    3. Ejecutar la purga.
    4. Verificar que la expirada desapareció y la vigente persiste.
    """
    # ── Setup ──────────────────────────────────────────────────────────────
    id_expirada = uuid.uuid4()
    id_vigente = uuid.uuid4()

    fila_expirada = PiiVault(
        id=id_expirada,
        student_matrix_id="@purge_test:localhost",
        interaction_id="purge_test_expired",
        token="[PERSON_PURGE_EXPIRED]",
        raw_value_encrypted="encrypted_dummy_expired",
        entity_type="PERSON",
        expires_at=datetime.datetime.utcnow() - datetime.timedelta(seconds=1),
    )
    fila_vigente = PiiVault(
        id=id_vigente,
        student_matrix_id="@purge_test:localhost",
        interaction_id="purge_test_valid",
        token="[PERSON_PURGE_VALID]",
        raw_value_encrypted="encrypted_dummy_valid",
        entity_type="PERSON",
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=90),
    )

    db.add(fila_expirada)
    db.add(fila_vigente)
    db.commit()

    # ── Ejecutar purga ──────────────────────────────────────────────────────
    eliminadas = _purge_expired(db)
    assert eliminadas >= 1, f"La purga debería eliminar ≥1 fila, eliminó {eliminadas}"

    # ── Verificaciones ──────────────────────────────────────────────────────
    # La expirada ya no existe
    result_exp = db.query(PiiVault).filter_by(id=id_expirada).first()
    assert result_exp is None, "La fila expirada sigue en BD después de la purga"

    # La vigente sigue existiendo
    result_vig = db.query(PiiVault).filter_by(id=id_vigente).first()
    assert result_vig is not None, "La fila vigente fue eliminada incorrectamente"

    # ── Limpieza ────────────────────────────────────────────────────────────
    db.query(PiiVault).filter_by(id=id_vigente).delete()
    db.commit()
