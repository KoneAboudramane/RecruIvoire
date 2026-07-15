#!/bin/bash
# ── Script de deploiement RecrutePro ─────────────────────────────────────────
# Usage : bash deploy.sh
# Prerequis : Ubuntu/Debian, Python 3.14, PostgreSQL, Redis, Nginx, Supervisor

set -e

APP_DIR="/home/deploy/recrutement"
VENV_DIR="$APP_DIR/venv"

echo "=== Mise a jour du code ==="
cd "$APP_DIR"
git pull origin main

echo "=== Activation du virtualenv ==="
source "$VENV_DIR/bin/activate"

echo "=== Installation des dependances ==="
pip install -r requirements.txt

echo "=== Installation de Playwright (Chromium) ==="
playwright install chromium

echo "=== Migrations base de donnees ==="
python manage.py migrate --noinput

echo "=== Collecte des fichiers statiques ==="
python manage.py collectstatic --noinput

echo "=== Creation du dossier logs ==="
mkdir -p "$APP_DIR/logs"

echo "=== Redemarrage des services ==="
sudo supervisorctl restart recrutement:*

echo "=== Deploiement termine ==="
echo "Verifier : sudo supervisorctl status recrutement:*"
