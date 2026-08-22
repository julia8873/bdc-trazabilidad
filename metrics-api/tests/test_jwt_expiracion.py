import pytest
import jwt
import datetime
from metrics_api.auth import JWT_SECRET_KEY, JWT_ALGORITHM
from metrics_api.models import AuditoriaAcceso

def test_expired_jwt(client, db_session):
    payload = {
        "sub": "student_expired",
        "moodle_user_id": 1,
        "is_teacher": False,
        "allowed_courses": [1],
        "exp": datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/v1/metrics/cursos/1/estudiantes/1", headers=headers)
    assert response.status_code == 401
    
    log = db_session.query(AuditoriaAcceso).filter_by(moodle_username="student_expired").first()
    assert log is not None
    assert log.resultado == "EXPIRED_JWT"
