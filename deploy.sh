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

echo "[4/4] Запуск сервера на порту 1298..."

# Убиваем старый процесс если уже висит на 1298
OLD_PID=$(lsof -ti tcp:1298 2>/dev/null || true)
if [ -n "$OLD_PID" ]; then
    echo "  → Останавливаем старый процесс (PID $OLD_PID)..."
    kill "$OLD_PID"
    sleep 1
fi

# Запуск в фоне, логи пишутся в server.log
nohup python manage.py runserver 0.0.0.0:1298 >> server.log 2>&1 &
echo $! > server.pid

echo ""
echo "✓ Сервер запущен в фоне (PID $(cat server.pid))"
echo "  Логи: tail -f server.log"
echo "  Стоп: kill \$(cat server.pid)"
