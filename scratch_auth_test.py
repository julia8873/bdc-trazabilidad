import requests

API_URL = "http://localhost:8000"

print("1. Login for alumno1")
sess = requests.Session()
r1 = sess.post(f"{API_URL}/token", json={"username": "alumno1", "password": "Alumno1!"})
print("Login status:", r1.status_code)
orig_token = sess.cookies.get("refresh_token")
print("Original token:", orig_token[:10] + "...")

print("\n2. Normal refresh (consumes token)")
r2 = sess.post(f"{API_URL}/refresh")
print("Refresh status:", r2.status_code)
new_token = sess.cookies.get("refresh_token")
print("New token:", new_token[:10] + "...")

print("\n3. Triggering reuse detection using revoked token")
sess_theft = requests.Session()
sess_theft.cookies.set("refresh_token", orig_token, domain="localhost", path="/")
r3 = sess_theft.post(f"{API_URL}/refresh")
print("Theft attempt status:", r3.status_code)
print("Theft attempt response:", r3.text)

