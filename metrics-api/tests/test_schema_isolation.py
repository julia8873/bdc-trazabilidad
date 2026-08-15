import pytest
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import text
from metrics_api.db import get_session

def test_metrics_user_cannot_read_public_mapeos():
    """
    Test que verifica el aislamiento de esquema (Fase 2).
    Asegura que el usuario `metrics_user` no tiene acceso a leer las tablas
    del esquema `public` de la base de datos `mapeo_db`, demostrando el
    uso correcto de REVOKE ALL ON SCHEMA public FROM metrics_user.
    """
    session = next(get_session())
    try:
        with pytest.raises(ProgrammingError) as exc_info:
            # Intento de leer de una tabla que sabemos que existe en public
            session.execute(text("SELECT * FROM public.mapeos"))
        
        # psycopg2 throws ProgrammingError for permission denied
        error_msg = str(exc_info.value)
        assert "permission denied for table mapeos" in error_msg or "permission denied for schema public" in error_msg
    finally:
        session.close()
