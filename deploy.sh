#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[1/4] Обновление кода..."
git pull origin main

echo "[2/4] Виртуальное окружение..."
[ ! -d venv ] && python3 -m venv venv
source venv/bin/activate

echo "[3/4] Зависимости + миграции..."
pip install -q -r requirements.txt
python manage.py migrate --noinput

echo "[4/4] Запуск на порту 1298..."
python manage.py runserver 0.0.0.0:1298
