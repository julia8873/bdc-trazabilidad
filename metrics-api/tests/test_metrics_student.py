import os
import jwt
from metrics_api.models import Interaccion
from datetime import datetime
from metrics_api.auth import JWT_SECRET_KEY, JWT_ALGORITHM

payload = {
    "sub": "teacher_mock",
    "moodle_user_id": 100,
    "is_teacher": True,
    "allowed_courses": [1, 2, 999]
}
token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
headers = {"Authorization": f"Bearer {token}"}

def test_student_zero_data(client):
    """Test explícito de cero datos, como pidió el usuario."""
    response = client.get("/v1/metrics/cursos/999/estudiantes/999", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["student_id"] == 999
    assert data["course_id"] == 999
    assert data["total_interactions"] == 0
    assert data["interactions_by_type"] == {}

def test_student_exists_but_not_in_course(client, db_session):
    """
    Test para el caso: alumno existe (tiene registros en interacciones en otro curso)
    pero no está matriculado/no tiene interacciones en el course_id indicado.
    """
    # Alumno 1 en curso 1
    db_session.add(Interaccion(moodle_user_id=1, moodle_course_id=1, tipo_interaccion="chat", timestamp=datetime.utcnow()))
    db_session.commit()

    # Consultamos al alumno 1 pero en curso 2
    response = client.get("/v1/metrics/cursos/2/estudiantes/1", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["student_id"] == 1
    assert data["course_id"] == 2
    assert data["total_interactions"] == 0
    assert data["interactions_by_type"] == {}

def test_student_with_data(client, db_session):
    # Alumno 1 en curso 1 con 2 chats
    db_session.add(Interaccion(moodle_user_id=1, moodle_course_id=1, tipo_interaccion="chat", timestamp=datetime.utcnow()))
    db_session.add(Interaccion(moodle_user_id=1, moodle_course_id=1, tipo_interaccion="chat", timestamp=datetime.utcnow()))
    db_session.commit()

    response = client.get("/v1/metrics/cursos/1/estudiantes/1", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_interactions"] == 2
    assert data["interactions_by_type"] == {"chat": 2}

def test_student_interactions_pagination_zero_data(client):
    response = client.get("/v1/metrics/cursos/2/estudiantes/1/interacciones", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0

def test_student_interactions_pagination_limits(client):
    # Invalid limit < 1
    response = client.get("/v1/metrics/cursos/1/estudiantes/1/interacciones?limit=0", headers=headers)
    assert response.status_code == 422
    
    # Invalid limit > 100
    response = client.get("/v1/metrics/cursos/1/estudiantes/1/interacciones?limit=101", headers=headers)
    assert response.status_code == 422

    # Invalid offset < 0
    response = client.get("/v1/metrics/cursos/1/estudiantes/1/interacciones?offset=-1", headers=headers)
    assert response.status_code == 422

def test_student_interactions_with_data(client, db_session):
    # Alumno 1 en curso 1 con 2 interacciones
    db_session.add(Interaccion(moodle_user_id=1, moodle_course_id=1, tipo_interaccion="chat", timestamp=datetime.utcnow()))
    db_session.add(Interaccion(moodle_user_id=1, moodle_course_id=1, tipo_interaccion="wiki", timestamp=datetime.utcnow()))
    db_session.commit()

    response = client.get("/v1/metrics/cursos/1/estudiantes/1/interacciones", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["tipo_interaccion"] in ("chat", "wiki")
