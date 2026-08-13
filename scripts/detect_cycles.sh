#!/bin/bash
set -e

# Script simulado de detección de dependencias cíclicas
# En producción, esto parseará requirements.txt / package.json de ambos repositorios.
# Aquí usamos un manifiesto de prueba para demostrar el bloqueo del CI.

echo "Analizando grafo de dependencias cruzadas entre repositorios..."

MOCK_DEPS="mock_deps.txt"

if [ ! -f "$MOCK_DEPS" ]; then
    echo "[OK] No hay dependencias declaradas (MOCK_DEPS ausente). Ignorando."
    exit 0
fi

if grep -q "CYCLE" "$MOCK_DEPS"; then
    echo "[ERROR] Dependencia Cíclica detectada en el grafo de módulos:"
    echo "  >> bdc-trazabilidad/metrics-api -> llm-wiki-assistant/shared-pkg"
    echo "  >> llm-wiki-assistant/shared-pkg -> bdc-trazabilidad/metrics-api"
    echo "Abortando el build de CI."
    exit 1
fi

echo "[OK] Grafo limpio. No se detectaron ciclos de dependencia."
exit 0
