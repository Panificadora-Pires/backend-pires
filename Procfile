web: sh -c 'exec uvicorn app.asgi:application --host 0.0.0.0 --port "${PORT:-5000}" --ws wsproto'
release: python manage.py migrate --noinput