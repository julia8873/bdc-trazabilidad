import pytest
import jwt
from metrics_api.auth import JWT_SECRET_KEY, JWT_ALGORITHM

def test_course_not_enrolled(client, db_session):
    payload = {
        "sub": "student_course",
        "moodle_user_id": 10,
        "is_teacher": False,
        "allowed_courses": [5]
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/v1/metrics/cursos/6/estudiantes/10", headers=headers)
    assert response.status_code == 403
    assert "Acceso denegado a este curso" in response.json()["detail"]
