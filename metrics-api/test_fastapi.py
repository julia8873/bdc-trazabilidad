from fastapi.testclient import TestClient
from metrics_api.main import app
from metrics_api.db import get_session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# We will use the real app with a test client to bypass HTTP networking issues
client = TestClient(app)

print("1. Login for alumno1")
r1 = client.post("/token", json={"username": "alumno1", "password": "Alumno1!"})
print("Login status:", r1.status_code)
# Extract cookie
cookies = client.cookies
orig_token = cookies.get("refresh_token")
print("Original token generated (real URL-safe):", orig_token[:15] + "...")

print("\n2. Normal refresh (consumes token)")
r2 = client.post("/refresh", cookies={"refresh_token": orig_token})
print("Refresh status:", r2.status_code)
new_token = r2.cookies.get("refresh_token")
print("New token generated:", new_token[:15] + "...")

print("\n3. Triggering reuse detection using revoked original token")
# Manually inject the revoked token
r3 = client.post("/refresh", cookies={"refresh_token": orig_token})
print("Theft attempt status:", r3.status_code)
print("Theft attempt response:", r3.json())

print("\n4. Checking DB to confirm all sessions are purged for the user")
with next(get_session()) as session:
    from metrics_api.models import RefreshToken
    import hashlib
    # Alumno1 moodle_user_id = 2
    tokens = session.query(RefreshToken).filter(RefreshToken.moodle_user_id == 2).all()
    print("Tokens remaining in DB for user:", len(tokens))
    if len(tokens) == 0:
        print("SUCCESS: Reuse detection purged all sessions successfully!")
