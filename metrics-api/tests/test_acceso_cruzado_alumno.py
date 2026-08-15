import pytest
import jwt
from metrics_api.auth import JWT_SECRET_KEY, JWT_ALGORITHM

def test_cross_student_access(client, db_session):
    payload = {
        "sub": "student_1",
        "moodle_user_id": 1,
        "is_teacher": False,
        "allowed_courses": [1]
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to access another student's data in the SAME course
    response = client.get("/metrics/course/1/student/2", headers=headers)
    assert response.status_code == 403
    assert "No puedes ver las métricas de otro alumno" in response.json()["detail"]

def test_teacher_cross_student_access(client, db_session):
    payload = {
        "sub": "teacher_1",
        "moodle_user_id": 100,
        "is_teacher": True,
        "allowed_courses": [1]
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Teachers CAN access other student's data in their course
    response = client.get("/metrics/course/1/student/2", headers=headers)
    assert response.status_code == 200

def test_student_cannot_access_course_aggregates(client, db_session):
    payload = {
        "sub": "student_1",
        "moodle_user_id": 1,
        "is_teacher": False,
        "allowed_courses": [1]
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to access course aggregates
    response = client.get("/metrics/course/1", headers=headers)
    assert response.status_code == 403
    assert "Solo profesores pueden ver métricas del curso completo" in response.json()["detail"]
    
    # Try to access course interactions
    response = client.get("/metrics/course/1/interactions", headers=headers)
    assert response.status_code == 403
    assert "Solo profesores pueden ver métricas del curso completo" in response.json()["detail"]
