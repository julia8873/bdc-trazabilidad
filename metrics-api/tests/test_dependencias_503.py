import pytest
from unittest.mock import patch
import requests

def test_moodle_auth_503(client):
    with patch("metrics_api.main.requests.post", side_effect=requests.RequestException):
        response = client.post("/token", json={"username": "user", "password": "pwd"})
        assert response.status_code == 503
        assert response.json()["detail"] == "Moodle no disponible"

def test_mapeo_api_503(client):
    with patch("metrics_api.main.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"token": "dummy"}
        
        with patch("metrics_api.main.requests.get", side_effect=requests.RequestException):
            response = client.post("/token", json={"username": "user", "password": "pwd"})
            assert response.status_code == 503
            assert response.json()["detail"] == "Mapeo API no disponible"
