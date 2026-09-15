"""
Tests E2E del pipeline completo de PII.
Se ejecutan dentro del contenedor metrics-api donde localhost:8000 es la propia API.

Ejecutar con:
  docker compose exec metrics-api pytest test_pii_e2e_full.py -v
"""
import os
import jwt as pyjwt
import datetime
import uuid
import requests
import pytest
from sqlalchemy import create_engine, text

METRICS_API_URL = "http://localhost:8000"
INTERNAL_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "dev_internal_token")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev_secret_key_for_local_testing_only")
JWT_ALGORITHM = "HS256"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://metrics_user:metrics_pass@postgres:5432/mapeo_db"
)
PII_SECRET_KEY = os.getenv("PII_SECRET_KEY", "")


def _make_teacher_jwt(username: str = "profesor_e2e_test") -> str:
    payload = {
        "sub": username,
        "is_teacher": True,
        "allowed_courses": [1, 2, 3],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    }
    return pyjwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _db_engine():
    return create_engine(
        DATABASE_URL,
        connect_args={"options": "-csearch_path=metrics"}
    )


# ── E2E-1: vault almacena y rechaza acceso sin autenticación ───────────────
def test_e2e_1_vault_almacena_y_bloquea_sin_auth():
    """Insertar en vault (201) → revelar sin JWT (401)."""
    interaction_id = f"e2e1_{uuid.uuid4().hex[:8]}"

    r = requests.post(
        f"{METRICS_API_URL}/internal/pii/vault",
        json={
            "student_matrix_id": "@e2e_user:localhost",
            "interaction_id": interaction_id,
            "mappings": [
                {"token": "[PERSON_1]", "raw_value": "Juan Pérez E2E", "entity_type": "PERSON"}
            ],
        },
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
    )
    assert r.status_code == 201, f"Error en vault: {r.text}"

    r2 = requests.post(
        f"{METRICS_API_URL}/v1/metrics/pii/reveal",
        json={"token": "[PERSON_1]", "interaction_id": interaction_id},
    )
    assert r2.status_code in (401, 403), (
        f"Debería rechazar sin JWT, devolvió {r2.status_code}: {r2.text}"
    )

    # Limpieza
    engine = _db_engine()
    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM metrics.pii_vault WHERE interaction_id = :iid"),
            {"iid": interaction_id},
        )
        conn.commit()


# ── E2E-2: reversión auditada con JWT de profesor ─────────────────────────
def test_e2e_2_reveal_con_profesor_devuelve_valor_y_audita():
    """
    1. Insertar en vault.
    2. Reveal con JWT de profesor → raw_value correcto.
    3. Verificar fila en pii_access_log directamente en BD.
    """
    interaction_id = f"e2e2_{uuid.uuid4().hex[:8]}"
    raw_original = "Ana García Auditada"

    # 1. Insertar en vault
    r_vault = requests.post(
        f"{METRICS_API_URL}/internal/pii/vault",
        json={
            "student_matrix_id": "@e2e_audit:localhost",
            "interaction_id": interaction_id,
            "mappings": [
                {"token": "[PERSON_1]", "raw_value": raw_original, "entity_type": "PERSON"}
            ],
        },
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
    )
    assert r_vault.status_code == 201, f"Vault error: {r_vault.text}"

    # 2. Reveal con JWT de profesor
    teacher_jwt = _make_teacher_jwt()
    r_reveal = requests.post(
        f"{METRICS_API_URL}/v1/metrics/pii/reveal",
        json={"token": "[PERSON_1]", "interaction_id": interaction_id},
        headers={"Authorization": f"Bearer {teacher_jwt}"},
    )
    assert r_reveal.status_code == 200, f"Reveal error: {r_reveal.text}"

    # 3. Valor devuelto es el original
    data = r_reveal.json()
    assert data.get("raw_value") == raw_original, (
        f"Valor incorrecto: esperado '{raw_original}', obtenido '{data.get('raw_value')}'"
    )

    # 4. Verificar pii_access_log en BD
    engine = _db_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id FROM metrics.pii_access_log "
                "WHERE interaction_id = :iid AND token_requested = :tok "
                "ORDER BY timestamp DESC LIMIT 1"
            ),
            {"iid": interaction_id, "tok": "[PERSON_1]"},
        ).fetchone()
    assert row is not None, (
        "No se creó fila en pii_access_log después del reveal"
    )

    # Limpieza
    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM metrics.pii_access_log WHERE interaction_id = :iid"),
            {"iid": interaction_id},
        )
        conn.execute(
            text("DELETE FROM metrics.pii_vault WHERE interaction_id = :iid"),
            {"iid": interaction_id},
        )
        conn.commit()


# ── E2E-3: insert cifrado + decrypt real contra Postgres ───────────────────
def test_e2e_3_pipeline_vault_db_insert_y_decrypt():
    """
    1. Insertar vía /internal/pii/vault.
    2. Leer raw_value_encrypted de Postgres.
    3. Verificar que NO está en claro.
    4. Descifrar con PII_SECRET_KEY → coincide con el original.
    """
    if not PII_SECRET_KEY:
        pytest.skip("PII_SECRET_KEY no configurado")

    interaction_id = f"e2e3_{uuid.uuid4().hex[:8]}"
    raw_original = "Rosario Valpuesta NIE X9876543B"

    # 1. Insertar
    r = requests.post(
        f"{METRICS_API_URL}/internal/pii/vault",
        json={
            "student_matrix_id": "@e2e_db:localhost",
            "interaction_id": interaction_id,
            "mappings": [
                {"token": "[PERSON_1]", "raw_value": raw_original, "entity_type": "PERSON"}
            ],
        },
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
    )
    assert r.status_code == 201, f"Vault error: {r.text}"

    # 2. Leer desde BD
    engine = _db_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT raw_value_encrypted FROM metrics.pii_vault "
                "WHERE interaction_id = :iid AND token = :tok"
            ),
            {"iid": interaction_id, "tok": "[PERSON_1]"},
        ).fetchone()

    assert row is not None, "No se encontró la fila en pii_vault"
    encrypted = row[0]

    # 3. No está en claro
    assert raw_original not in encrypted, "¡raw_value en claro en BD!"

    # 4. Descifrar y verificar
    from cryptography.fernet import Fernet
    f = Fernet(PII_SECRET_KEY.encode())
    decrypted = f.decrypt(encrypted.encode()).decode()
    assert decrypted == raw_original, (
        f"Descifrado incorrecto: esperado '{raw_original}', obtenido '{decrypted}'"
    )

    # Limpieza
    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM metrics.pii_vault WHERE interaction_id = :iid"),
            {"iid": interaction_id},
        )
        conn.commit()
