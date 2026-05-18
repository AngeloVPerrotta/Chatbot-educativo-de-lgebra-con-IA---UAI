#!/bin/bash
# =============================================================================
# ALGORIA - Script de instalación para VPS Ubuntu (Hostinger Cloud Startup)
# Dominio: algoria.angeloperrotta.online
# =============================================================================

set -euo pipefail

REPO_URL="https://github.com/AngeloVPerrotta/Chatbot-educativo-de-lgebra-con-IA---UAI.git"
APP_DIR="/opt/algoria"
DOMAIN="algoria.angeloperrotta.online"

# Verificar que se ejecuta como root
if [ "$EUID" -ne 0 ]; then
    echo "Error: Ejecutá este script como root (sudo bash hostinger-setup.sh)"
    exit 1
fi

echo "=========================================="
echo "  ALGORIA - Instalación en VPS Ubuntu"
echo "=========================================="

# --- 1. Actualizar sistema ---
echo "[1/11] Actualizando sistema..."
apt update && apt upgrade -y

# --- 2. Instalar Python 3.11 ---
echo "[2/11] Instalando Python 3.11..."
apt install software-properties-common -y
add-apt-repository ppa:deadsnakes/ppa -y
apt update
apt install python3.11 python3.11-venv python3-pip -y

# --- 3. Instalar Nginx ---
echo "[3/11] Instalando Nginx..."
apt install nginx -y

# --- 4. Clonar repositorio ---
echo "[4/11] Clonando repositorio..."
if [ -d "$APP_DIR" ]; then
    echo "  -> $APP_DIR ya existe, haciendo git pull..."
    cd "$APP_DIR" && git pull
else
    git clone "$REPO_URL" "$APP_DIR"
fi

# --- 5. Crear entorno virtual ---
echo "[5/11] Creando entorno virtual..."
python3.11 -m venv "$APP_DIR/venv"

# --- 6. Instalar dependencias ---
echo "[6/11] Instalando dependencias de Python..."
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

# --- 7. Crear archivo .env ---
echo "[7/11] Creando archivo .env..."
if [ ! -f "$APP_DIR/.env" ]; then
    cat > "$APP_DIR/.env" << 'EOF'
# ALGORIA - Variables de entorno (completar con valores reales)
ANTHROPIC_API_KEY=sk-ant-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
ADMIN_PIN=CAMBIAR_ESTE_PIN
MP_ACCESS_TOKEN=CAMBIAR_ESTE_TOKEN
ADMIN_KEY=CAMBIAR_ESTA_KEY
ENVIRONMENT=production
EOF
    chmod 600 "$APP_DIR/.env"
    echo "  -> .env creado. IMPORTANTE: Editá /opt/algoria/.env con tus claves reales."
else
    echo "  -> .env ya existe, no se sobreescribe."
fi

# --- 8. Crear servicio systemd ---
echo "[8/11] Creando servicio systemd..."
cat > /etc/systemd/system/algoria.service << EOF
[Unit]
Description=Algoria - Chatbot educativo de Álgebra con IA
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR/backend
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable algoria

# --- 9. Crear config de Nginx ---
echo "[9/11] Configurando Nginx..."
cat > /etc/nginx/sites-available/algoria << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }
}
EOF

# --- 10. Habilitar sitio y reiniciar Nginx ---
echo "[10/11] Habilitando sitio en Nginx..."
ln -sf /etc/nginx/sites-available/algoria /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

# --- 11. Instalar Certbot y generar SSL ---
echo "[11/11] Instalando Certbot y generando certificado SSL..."
apt install certbot python3-certbot-nginx -y
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email

# --- Iniciar servicio ---
echo ""
echo "Iniciando servicio Algoria..."
systemctl start algoria

echo ""
echo "=========================================="
echo "  INSTALACIÓN COMPLETADA"
echo "=========================================="
echo ""
echo "  URL:     https://$DOMAIN"
echo "  Logs:    journalctl -u algoria -f"
echo "  Estado:  systemctl status algoria"
echo ""
echo "  IMPORTANTE: Editá /opt/algoria/.env con tus claves reales"
echo "  y luego reiniciá: systemctl restart algoria"
echo ""
