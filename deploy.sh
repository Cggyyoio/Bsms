#!/usr/bin/env bash
# deploy.sh — One-command VPS setup
set -e

BOT_USER="botuser"
BOT_DIR="/home/${BOT_USER}/otp_bot"
SERVICE="otp_bot"

echo "==> [1/5] Creating user '${BOT_USER}'..."
id "${BOT_USER}" &>/dev/null || useradd -m -s /bin/bash "${BOT_USER}"

echo "==> [2/5] Installing dependencies..."
apt-get update -q && apt-get install -y -q python3 python3-pip python3-venv

echo "==> [3/5] Copying files..."
mkdir -p "${BOT_DIR}"
cp -r . "${BOT_DIR}/"
chown -R "${BOT_USER}:${BOT_USER}" "${BOT_DIR}"

echo "==> [4/5] Setting up virtualenv..."
sudo -u "${BOT_USER}" bash -c "
  cd ${BOT_DIR}
  python3 -m venv venv
  venv/bin/pip install -q --upgrade pip
  venv/bin/pip install -q -r requirements.txt
"

echo "==> [5/5] Installing systemd service..."
cat > /etc/systemd/system/${SERVICE}.service << EOF
[Unit]
Description=OTP Telegram Bot (Durian)
After=network-online.target

[Service]
User=${BOT_USER}
WorkingDirectory=${BOT_DIR}
ExecStart=${BOT_DIR}/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE}"

echo ""
echo "✅ Done! Next steps:"
echo "  1. cp ${BOT_DIR}/.env.example ${BOT_DIR}/.env"
echo "  2. nano ${BOT_DIR}/.env"
echo "  3. systemctl start ${SERVICE}"
echo "  4. journalctl -u ${SERVICE} -f"
