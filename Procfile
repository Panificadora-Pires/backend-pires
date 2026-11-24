web: sh -c 'exec uvicorn app.asgi:application --host 0.0.0.0 --port "${PORT:-5000}" --ws wsproto --workers 2 --log-level info'
release: python manage.py migrate --noinput
