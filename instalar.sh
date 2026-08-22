#!/bin/bash
set -e

MODE=${1:-dev}

echo "=== bdc-trazabilidad: Preparando entorno ($MODE) ==="

# Asegurar que la red bdc-net existe (idempotente)
if ! docker network inspect bdc-net >/dev/null 2>&1; then
    echo "=> Creando red externa 'bdc-net'..."
    docker network create bdc-net
else
    echo "=> La red 'bdc-net' ya existe."
fi

if [ "$MODE" = "--test" ]; then
    echo "=> Modo Test: Ejecutando suite completa de consolidación (Fase 8)"
    
    # Preparamos las variables para el reporte final
    declare -A RESULTS
    declare -A TIMES
    
    run_block() {
        local name=$1
        local cmd=$2
        echo "=== Iniciando Bloque: $name ==="
        local start_time=$(date +%s)
        
        if eval "$cmd"; then
            RESULTS["$name"]="PASSED"
        else
            RESULTS["$name"]="FAILED"
        fi
        
        local end_time=$(date +%s)
        TIMES["$name"]=$((end_time - start_time))
        echo "=== Fin Bloque: $name (${RESULTS["$name"]}) ==="
    }

    # Bloque 1: API
    run_block "API" "docker exec -e PYTHONPATH=/app bdc-trazabilidad-metrics-api-1 pytest tests/"
    
    # Bloque 2: Worker
    run_block "Worker" "docker exec -e PYTHONPATH=/app:/shared-pkg bdc-trazabilidad-metrics-worker-1 pytest tests/"
    
    # Bloque 3: Mapeo-API (Copiando tests al contenedor en vuelo ya que no están en la imagen prod)
    docker exec moodle-matrix-dev-mapeo-api-1 rm -rf /code/tests
    docker cp ../llm-wiki-assistant/moodle-matrix-dev/mapeo-api/tests moodle-matrix-dev-mapeo-api-1:/code/tests
    run_block "Mapeo-API" "docker exec -e DATABASE_URL=postgresql://mapeo_user:mapeo_db_pass@postgres:5432/mapeo_test_db moodle-matrix-dev-mapeo-api-1 alembic upgrade head >/dev/null 2>&1 && docker exec -e DATABASE_URL=postgresql://mapeo_user:mapeo_db_pass@postgres:5432/mapeo_test_db -e PYTHONPATH=/code moodle-matrix-dev-mapeo-api-1 pytest tests/"
    
    # Bloque 4: Frontend E2E
    run_block "Frontend-E2E" 'docker run --rm --network bdc-net -v $(pwd)/frontend:/app -w /app mcr.microsoft.com/playwright:v1.41.0-jammy sh -c "npm install && npx playwright test e2e/ --reporter=list"'
    
    # Bloque 5: Documentacion
    run_block "Documentacion" '(cd ../llm-wiki-assistant && (cat Doxyfile; echo "WARN_AS_ERROR=YES") | doxygen -) && (cd ../bdc-trazabilidad && (cat Doxyfile; echo "WARN_AS_ERROR=YES") | doxygen -)'
    
    # Bloque 6: Orquestacion
    run_block "Orquestacion" "docker compose config -q && docker compose -f deploy/docker-compose.prod.yml config -q"
    
    # Bloque 7: Compatibilidad Cruzada
    run_block "Compatibilidad" "bash scripts/test_cross_compat.sh"
    
    # Bloque 8: True E2E
    echo "=== Iniciando Bloque: True-E2E ==="
    run_block "True-E2E" "docker run --rm --network bdc-net -v $(pwd):/workspace -v $(pwd)/../llm-wiki-assistant/shared-pkg:/shared-pkg -w /workspace -e PYTHONPATH=/workspace:/shared-pkg:/workspace/metrics-worker:/workspace/metrics-api -e GITHUB_PAT=${GITHUB_PAT} -e GITHUB_TOKEN=${GITHUB_PAT} -e MAPEO_API_TOKEN=8f3b2a9d8f3b2a9d8f3b2a9d8f3b2a9d -e ENABLE_DEMO_AUTH=true -e MAPEO_API_URL=http://127.0.0.1:8001 -e DATABASE_URL=postgresql://mapeo_user:mapeo_db_pass@postgres:5432/mapeo_test_db -e E2E_TEST_FORK_URL=${E2E_TEST_FORK_URL:-https://github.com/julia8873/e2e-test-repo.git} moodle-matrix-dev-mapeo-api sh -c \"apt-get update >/dev/null 2>&1 && apt-get install -y git >/dev/null 2>&1 && cd /code && alembic upgrade head >/dev/null 2>&1 && python -c \\\"import psycopg2, os; conn=psycopg2.connect(os.environ['DATABASE_URL']); cur=conn.cursor(); cur.execute('CREATE SCHEMA IF NOT EXISTS metrics;'); conn.commit()\\\" && cd /workspace/metrics-api && alembic upgrade head >/dev/null 2>&1 && cd /code && (uvicorn app.main:app --port 8001 --host 127.0.0.1 >/workspace/uvicorn.log 2>&1 &) && sleep 5 && cd /workspace && python scripts/run_true_e2e.py\""

    echo ""
    echo "=== TABLA RESUMEN ==="
    printf "%-20s | %-10s | %-10s\n" "BLOQUE" "RESULTADO" "TIEMPO (s)"
    printf "%-20s-+-%-10s-+-%-10s\n" "--------------------" "----------" "----------"
    for block in "API" "Worker" "Mapeo-API" "Frontend-E2E" "Documentacion" "Orquestacion" "Compatibilidad" "True-E2E"; do
        printf "%-20s | %-10s | %-10s\n" "$block" "${RESULTS[$block]:-SKIPPED}" "${TIMES[$block]:-0}"
    done
    echo "====================="
    exit 0
fi

if [ "$MODE" = "production" ] || [ "$MODE" = "--env=production" ]; then
    echo "=> Modo producción: Ejecutando healthchecks estrictos (fail-fast)..."
    
    # Comprobar postgres
    if ! docker run --rm --network bdc-net alpine nc -z postgres 5432; then
        echo "ERROR: Postgres (postgres) no está disponible en bdc-net."
        exit 1
    fi
    echo "  [OK] Postgres detectado."

    # Comprobar redis
    if ! docker run --rm --network bdc-net alpine nc -z redis 6379; then
        echo "ERROR: Redis no está disponible en bdc-net."
        exit 1
    fi
    echo "  [OK] Redis detectado."

    # Comprobar mapeo-api
    if ! docker run --rm --network bdc-net alpine nc -z mapeo-api 8000; then
        echo "ERROR: mapeo-api no está disponible en bdc-net."
        exit 1
    fi
    echo "  [OK] mapeo-api detectado."

    export MOCK_SERVICES=false
    echo "=> Levantando servicios (producción)..."
    docker compose -f deploy/docker-compose.prod.yml up -d
else
    echo "=> Modo desarrollo: MOCK_SERVICES=true"
    export MOCK_SERVICES=true
    docker compose up -d
fi

echo "=== Listo ==="
