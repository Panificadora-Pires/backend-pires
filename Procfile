web: uvicorn app.asgi:application --host 0.0.0.0 --port 5000 --ws wsproto --workers 2 --log-level info
release: python manage.py migrate --noinput
