import pytest

def test_compat():
    try:
        from shared_pkg.okf_contract import COMMIT_MSG_INGEST, COMMIT_MSG_REVERT, COMMIT_MSG_SYNC, OKF_CONTRACT_VERSION, PATH_LOG_INTERACCIONES
    except ImportError as e:
        pytest.fail(f"Contrato roto: no se pudo importar las constantes esperadas: {e}")
    
    # Validaciones fuertes de contrato
    assert COMMIT_MSG_INGEST == "Ingesta automatica de conceptos", "El mensaje de Ingesta automatica de conceptos ha cambiado en origen sin versionar"
    assert COMMIT_MSG_SYNC == "Sincronización automática completa de material oficial", "El mensaje de Sincronizacion automatica completa de material oficial ha cambiado"
    assert PATH_LOG_INTERACCIONES == "logs/interacciones", "La ruta de interacciones ha cambiado"
    assert OKF_CONTRACT_VERSION == "1.0.0", "Version de contrato no compatible"
