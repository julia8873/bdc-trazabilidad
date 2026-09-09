import os
import requests

METRICS_API_URL = "http://localhost:8000"
INTERNAL_TOKEN = "dev_internal_token"

vault_url = f"{METRICS_API_URL}/internal/pii/vault"
payload = {
    "student_matrix_id": "@test_user:localhost",
    "interaction_id": "test_interaction_e2e",
    "mappings": [
        {"token": "[PERSON_1]", "raw_value": "Juan Pérez E2E", "entity_type": "PERSON"}
    ]
}
headers = {"Authorization": f"Bearer {INTERNAL_TOKEN}"}
resp = requests.post(vault_url, json=payload, headers=headers)
print("Vault response:", resp.status_code, resp.text)
assert resp.status_code == 201

reveal_url = f"{METRICS_API_URL}/v1/metrics/pii/reveal"
resp2 = requests.post(reveal_url, json={"token": "[PERSON_1]", "interaction_id": "test_interaction_e2e"})
print("Reveal no-auth response:", resp2.status_code, resp2.text)
assert resp2.status_code in [401, 403]
print("All passed!")
