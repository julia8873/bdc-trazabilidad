import os
from metrics_api.models import Interaccion
from datetime import datetime

import jwt
from metrics_api.auth import JWT_SECRET_KEY, JWT_ALGORITHM

payload = {
    "sub": "teacher_mock",
    "moodle_user_id": 100,
    "is_teacher": True,
    "allowed_courses": [1, 2, 999]
}
token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
headers = {"Authorization": f"Bearer {token}"}

def test_pagination_courses_out_of_bounds(client, db_session):
    # Insertamos 5 elementos
    for _ in range(5):
        db_session.add(Interaccion(moodle_user_id=1, moodle_course_id=1, tipo_interaccion="chat"))
    db_session.commit()

    # Offset más grande que total
    response = client.get("/metrics/course/1/interactions?limit=10&offset=10", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 0

def test_pagination_courses_correct_pages(client, db_session):
    for i in range(15):
        db_session.add(Interaccion(moodle_user_id=1, moodle_course_id=1, tipo_interaccion="chat"))
    db_session.commit()

    # Página 1 (0-10)
    response = client.get("/metrics/course/1/interactions?limit=10&offset=0", headers=headers)
    data = response.json()
    assert data["total"] == 15
    assert len(data["items"]) == 10

    # Página 2 (10-20)
    response2 = client.get("/metrics/course/1/interactions?limit=10&offset=10", headers=headers)
    data2 = response2.json()
    assert data2["total"] == 15
    assert len(data2["items"]) == 5
