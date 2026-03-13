#!/bin/bash
# Деплой VOR на сервер — выполнять по шагам на сервере

set -e

echo "=== Шаг 2: Swap ==="
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h

echo "=== Шаг 3: Зависимости ==="
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git ffmpeg

echo "=== Шаг 5: Python venv ==="
cd ~/vor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "=== Шаг 8: systemd ==="
sudo cp deploy/vor-web.service /etc/systemd/system/
sudo cp deploy/vor-telegram.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vor-web vor-telegram
sudo systemctl start vor-web vor-telegram

echo "=== Шаг 9: Firewall ==="
sudo ufw allow 8001/tcp
sudo ufw allow 22/tcp
sudo ufw --force enable

echo "Done. Check: sudo systemctl status vor-web vor-telegram"
