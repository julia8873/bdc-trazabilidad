import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import jwt
from metrics_api.auth import JWT_SECRET_KEY, JWT_ALGORITHM

def get_token(is_teacher=True, allowed_courses=None):
    payload = {
        "sub": "user_mock",
        "moodle_user_id": 1,
        "is_teacher": is_teacher,
        "allowed_courses": allowed_courses or [1]
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def test_get_students_contract(client):
    """1. Test Unitario/Integración de Contrato"""
    token = get_token(is_teacher=True, allowed_courses=[1])
    
    # Mock requests.get to mapeo-api
    with patch("metrics_api.main.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"moodle_user_id": 2, "moodle_username": "alumno1", "repo_url": "http://github", "is_teacher": False}
        ]
        mock_get.return_value = mock_resp
        
        response = client.get("/v1/metrics/cursos/1/estudiantes", headers={"Authorization": f"Bearer {token}"})
        
        if response.status_code == 422:
            print("422 Error details:", response.json())
        assert response.status_code == 200
        data = response.json()
        assert data["course_id"] == 1
        assert len(data["students"]) == 1
        student = data["students"][0]
        assert "ultima_actividad" in student
        assert "estado_sincronizacion" in student
        assert student["estado_sincronizacion"] == "OK"


def test_roleguard_student_denied(client):
    """2. Test de Seguridad (RoleGuard) - alumno"""
    token = get_token(is_teacher=False, allowed_courses=[1])
    response = client.get("/v1/metrics/cursos/1/estudiantes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert "Solo profesores" in response.json()["detail"]


def test_roleguard_teacher_wrong_course(client):
    """2. Test de Seguridad (RoleGuard) - profesor curso equivocado"""
    # Teacher has access to course 2, but requests course 1
    token = get_token(is_teacher=True, allowed_courses=[2])
    response = client.get("/v1/metrics/cursos/1/estudiantes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert "No tienes permiso para ver los alumnos de este curso" in response.json()["detail"]

def test_roleguard_teacher_own_course_success(client):
    """Test de Seguridad (RoleGuard) - profesor viendo su propio curso (feliz)"""
    token = get_token(is_teacher=True, allowed_courses=[1])
    
    with patch("metrics_api.main.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_get.return_value = mock_resp
        
        response = client.get("/v1/metrics/cursos/1/estudiantes", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200


def test_demo_login_disabled(client):
    """3. Test de Seguridad (Demo Login Disabled)"""
    # We remove ENABLE_DEMO_AUTH explicitly
    with patch.dict(os.environ, {"ENABLE_DEMO_AUTH": "false", "MOODLE_AUTH_URL": "http://fake"}):
        with patch("metrics_api.main.requests.post") as mock_post:
            # Moodle authentication fails
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_post.return_value = mock_resp
            
            response = client.post("/token", json={"username": "profesor1", "password": "Profesor1!"})
            assert response.status_code == 401
