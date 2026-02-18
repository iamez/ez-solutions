# EZ Solutions — process definitions for Heroku / Railway / Render / Dokku
# Start all three process types in production:
#   web     — WSGI application server
#   worker  — Celery worker (default, provisioning, and periodic queues)
#   beat    — Celery Beat scheduler (run exactly ONE instance)
#
# Scale worker horizontally (e.g. `heroku ps:scale worker=2`).
# Never scale beat above 1 — duplicate Beat processes cause double-firing.

web: gunicorn config.wsgi:application --workers 4 --threads 2 --worker-class gthread --timeout 30 --bind 0.0.0.0:$PORT

worker: celery -A config worker --loglevel=info --queues=default,provisioning,periodic --concurrency=4 --hostname=worker@%h

beat: celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
