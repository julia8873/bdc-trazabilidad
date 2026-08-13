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

if [ "$MODE" = "production" ] || [ "$MODE" = "--env=production" ]; then
    echo "=> Modo producción: Ejecutando healthchecks estrictos (fail-fast)..."
    
    # Comprobar postgres
    if ! docker run --rm --network bdc-net alpine nc -z postgres 5432; then
        echo "ERROR: Postgres (db) no está disponible en bdc-net."
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
