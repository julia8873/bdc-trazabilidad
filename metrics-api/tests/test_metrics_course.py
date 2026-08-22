import os
import pytest
from unittest.mock import patch
from metrics_api.models import Interaccion
from datetime import datetime

import jwt
from metrics_api.auth import JWT_SECRET_KEY, JWT_ALGORITHM

payload = {
    "sub": "teacher_mock",
    "moodle_user_id": 1,
    "is_teacher": True,
    "allowed_courses": [1, 2, 999]
}
token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
headers = {"Authorization": f"Bearer {token}"}

def test_course_zero_data(client):
    """Test explícito de cero datos, como pidió el usuario."""
    response = client.get("/v1/metrics/cursos/999", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["course_id"] == 999
    assert data["total_interactions"] == 0
    assert data["interactions_by_type"] == {}
    assert data["percentiles"] == {
        "p25": 0.0,
        "p50": 0.0,
        "p75": 0.0,
        "p90": 0.0,
        "unique_users": 0
    }

def test_course_with_data(client, db_session):
    # Crear interacciones mock
    for i in range(5):
        interaccion = Interaccion(
            moodle_user_id=1, moodle_course_id=1, tipo_interaccion="chat", timestamp=datetime.utcnow()
        )
        db_session.add(interaccion)
    for i in range(3):
        interaccion = Interaccion(
            moodle_user_id=2, moodle_course_id=1, tipo_interaccion="quiz", timestamp=datetime.utcnow()
        )
        db_session.add(interaccion)
    db_session.commit()

    response = client.get("/v1/metrics/cursos/1", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_interactions"] == 8
    assert data["interactions_by_type"] == {"chat": 5, "quiz": 3}
    assert data["percentiles"]["unique_users"] == 2
    assert data["percentiles"]["p50"] == 4.0
    assert data["percentiles"]["p25"] == 3.5
    assert data["percentiles"]["p75"] == 4.5
    assert data["percentiles"]["p90"] == 4.8

def test_course_interactions_pagination_zero_data(client):
    response = client.get("/v1/metrics/cursos/999/interacciones", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0
    assert data["limit"] == 10
    assert data["offset"] == 0

def test_course_interactions_pagination_limits(client):
    # Invalid limit < 1
    response = client.get("/v1/metrics/cursos/1/interacciones?limit=0", headers=headers)
    assert response.status_code == 422
    
    # Invalid limit > 100
    response = client.get("/v1/metrics/cursos/1/interacciones?limit=101", headers=headers)
    assert response.status_code == 422

    # Invalid offset < 0
    response = client.get("/v1/metrics/cursos/1/interacciones?offset=-1", headers=headers)
    assert response.status_code == 422

def test_course_interactions_with_data(client, db_session):
    # Crear interacciones mock
    for i in range(5):
        interaccion = Interaccion(
            moodle_user_id=1, moodle_course_id=1, tipo_interaccion="chat", timestamp=datetime.utcnow()
        )
        db_session.add(interaccion)
    db_session.commit()

    response = client.get("/v1/metrics/cursos/1/interacciones", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 5
    assert data["items"][0]["tipo_interaccion"] == "chat"
