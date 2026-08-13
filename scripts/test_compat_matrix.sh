#!/bin/bash
set -e

# Script simulado de matriz de compatibilidad
# Valida la versión del paquete compartido provisto por llm-wiki-assistant

PKG_DIR="../llm-wiki-assistant/shared-pkg"
VERSION_FILE="${PKG_DIR}/version.txt"

if [ ! -f "$VERSION_FILE" ]; then
    echo "ERROR: No se encontró el paquete simulado en $VERSION_FILE"
    exit 1
fi

VERSION=$(cat "$VERSION_FILE")
echo "Probando compatibilidad contra shared-pkg v${VERSION}..."

if [ "$VERSION" == "1.0.0" ]; then
    echo "[OK] Versión 1.0.0 es compatible. Tests pasaron en bdc-trazabilidad."
    exit 0
elif [ "$VERSION" == "2.0.0-incompatible" ]; then
    echo "[ERROR] Versión $VERSION introduce breaking changes. Tests de integración fallaron."
    exit 1
else
    echo "[WARN] Versión $VERSION desconocida. Asumiendo fallo."
    exit 1
fi
