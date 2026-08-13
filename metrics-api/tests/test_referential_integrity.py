import pytest
import requests
import responses
from metrics_api.models import Interaccion

MAPEO_API_URL = "http://mapeo-api:8000"
MAPEO_API_TOKEN = "metrics_pass" # Assuming the test env uses this

def validate_moodle_user_sync(moodle_user_id: int, moodle_course_id: int) -> bool:
    """
    Simulación de la lógica síncrona que verificará si la tupla de user+course existe.
    En una app completa, esto estaría en un controlador o servicio.
    """
    headers = {"Authorization": f"Bearer {MAPEO_API_TOKEN}"}
    try:
        response = requests.get(
            f"{MAPEO_API_URL}/mapeos",
            params={"moodle_user_id": moodle_user_id, "moodle_course_id": moodle_course_id},
            headers=headers,
            timeout=2.0
        )
        response.raise_for_status()
        return len(response.json()) > 0
    except requests.exceptions.RequestException as e:
        # Comportamiento fail-fast
        raise RuntimeError(f"Fallo al validar integridad referencial contra mapeo-api: {str(e)}")


@responses.activate
def test_referential_integrity_mock_success():
    """
    Validación de la FK Lógica mediante llamadas mockeadas (usando responses)
    al endpoint GET /mapeos de mapeo-api.
    """
    responses.add(
        responses.GET,
        f"{MAPEO_API_URL}/mapeos",
        json=[{"id": 1, "moodle_user_id": 100, "moodle_course_id": 5}],
        status=200
    )

    is_valid = validate_moodle_user_sync(100, 5)
    assert is_valid is True


@responses.activate
def test_referential_integrity_mock_not_found():
    """
    Validación de que rechaza si mapeo-api no encuentra el mapeo.
    """
    responses.add(
        responses.GET,
        f"{MAPEO_API_URL}/mapeos",
        json={"detail": "Mapeo no encontrado"},
        status=404
    )

    with pytest.raises(RuntimeError) as exc_info:
        validate_moodle_user_sync(999, 999)
    assert "404 Client Error" in str(exc_info.value)


@responses.activate
def test_referential_integrity_fail_fast_service_down():
    """
    Comportamiento fail-fast en caso de que el servicio esté caído.
    Simulamos un ConnectionError sin devolver respuesta HTTP.
    """
    responses.add(
        responses.GET,
        f"{MAPEO_API_URL}/mapeos",
        body=requests.exceptions.ConnectionError("Connection refused")
    )

    with pytest.raises(RuntimeError) as exc_info:
        validate_moodle_user_sync(100, 5)
    assert "Connection refused" in str(exc_info.value)
