#!/bin/bash
pip install pytest requests fastapi httpx sqlalchemy alembic psycopg2-binary pyjwt pydantic-settings pydantic
export DATABASE_URL=postgresql://metrics_user:metrics_pass@moodle-matrix-dev-postgres-1:5432/mapeo_db
export PYTHONPATH=/app
pytest -v tests/test_trigger_sql.py tests/test_dependencias_503.py tests/test_log_auditoria.py tests/test_jwt_expiracion.py tests/test_acceso_curso_no_matriculado.py tests/test_acceso_cruzado_alumno.py > /app/pytest.log 2>&1
echo "Pytest finished with code $?" >> /app/pytest.log
