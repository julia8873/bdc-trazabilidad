import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

import jwt
from metrics_api.auth import JWT_SECRET_KEY, JWT_ALGORITHM

def test_auth_no_token(client):
    response = client.get("/v1/metrics/cursos/1")
    assert response.status_code in (401, 403)
    assert response.json()["detail"] == "Not authenticated"

def test_auth_invalid_token(client):
    response = client.get("/v1/metrics/cursos/1", headers={"Authorization": "Bearer wrong.token.here"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Token inválido"

def test_auth_valid_token(client):
    payload = {
        "sub": "teacher_mock",
        "moodle_user_id": 1,
        "is_teacher": True,
        "allowed_courses": [1, 2, 999]
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    response = client.get("/v1/metrics/cursos/1", headers={"Authorization": f"Bearer {token}"})
    print("STATUS:", response.status_code)
    print("JSON:", response.json())
    # 200 is expected because token is valid (assuming course 1 returns empty metrics)
    assert response.status_code == 200

def test_auth_fail_fast_no_env():
    # En este test instanciamos la app sin token a ver si el lifespan falla.
    # FastAPI lifespan events only run if we enter the context manager of TestClient.
    from metrics_api.main import app
    with patch.dict(os.environ, clear=True):
        with pytest.raises(RuntimeError, match="FATAL: MOODLE_AUTH_URL no está configurado."):
            with TestClient(app):
                pass
