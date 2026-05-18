#!/bin/bash
# =============================================================================
# ALGORIA - Script de actualización
# =============================================================================

set -euo pipefail

APP_DIR="/opt/algoria"

if [ "$EUID" -ne 0 ]; then
    echo "Error: Ejecutá este script como root (sudo bash update.sh)"
    exit 1
fi

echo "Actualizando Algoria..."

cd "$APP_DIR"
git pull
"$APP_DIR/venv/bin/pip" install -r backend/requirements.txt
systemctl restart algoria

echo "Actualización completada. Estado del servicio:"
systemctl status algoria --no-pager
