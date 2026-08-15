import pytest
from unittest.mock import patch
from metrics_api.models import AuditoriaAcceso
import jwt
from metrics_api.auth import JWT_SECRET_KEY, JWT_ALGORITHM
import datetime

def test_log_fallo_moodle(client, db_session):
    with patch("metrics_api.main.requests.post") as mock_post:
        mock_post.return_value.status_code = 401
        mock_post.return_value.json.return_value = {"auth": False}
        
        response = client.post("/token", json={"username": "testuser", "password": "badpassword"})
        assert response.status_code == 401
        
        log = db_session.query(AuditoriaAcceso).filter_by(moodle_username="testuser").first()
        assert log is not None
        assert log.resultado == "FAILED_MOODLE_AUTH"
        assert "password" not in str(log.metadatos)

def test_log_invalid_jwt(client, db_session):
    # Generamos un JWT pero lo manipulamos
    payload = {"sub": "student_invalid"}
    token = jwt.encode(payload, "wrong_secret", algorithm=JWT_ALGORITHM)
    
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/metrics/course/1", headers=headers)
    assert response.status_code == 401
    
    log = db_session.query(AuditoriaAcceso).filter_by(moodle_username="student_invalid").first()
    assert log is not None
    assert log.resultado == "INVALID_JWT"
