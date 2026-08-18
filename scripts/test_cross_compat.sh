#!/bin/bash
set -e

echo "=== Test de Compatibilidad Cruzada ==="

# 1. Ejecutar Detección de Ciclos
echo "-> Verificando ciclos de dependencia (pyproject.toml + integracion-bdc.md)..."
python3 scripts/detect_cycles.py

# 2. Parsear docs/integracion-bdc.md para verificar versiones
echo "-> Validando versión fijada en integracion-bdc.md (Regla 6)..."
MD_FILE="docs/integracion-bdc.md"

if [ ! -f "$MD_FILE" ]; then
    echo "[ERROR] No se encuentra $MD_FILE"
    exit 1
fi

# Buscar la linea de shared-pkg.okf_contract
# Formato: | llm-wiki-assistant -> bdc-trazabilidad | shared-pkg.okf_contract | Motivo | 1.0.0 | Fecha | ... |
VERSION=$(grep "shared-pkg.okf_contract" "$MD_FILE" | awk -F'|' '{print $5}' | xargs)

if [ -z "$VERSION" ]; then
    echo "[ERROR] No se pudo encontrar la versión de shared-pkg.okf_contract en $MD_FILE"
    exit 1
fi

if [ "$VERSION" = "main" ] || [ "$VERSION" = "latest" ]; then
    echo "[ERROR] La versión no puede ser '$VERSION'. Regla 6 violada."
    exit 1
fi

echo "[OK] Versión fijada correctamente: $VERSION"

# 3. Tests de paquetes transversales
echo "-> Ejecutando tests cruzados (worker) para verificar el contrato OKF..."
docker exec -e PYTHONPATH=/app:/shared-pkg bdc-trazabilidad-metrics-worker-1 pytest tests/test_compat.py

echo "=== Fin del Test de Compatibilidad Cruzada ==="
