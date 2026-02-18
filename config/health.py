from django.conf import settings
from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """Liveness probe — checks DB and Redis connectivity."""
    checks = {}

    # Database
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    # Redis (Celery broker) — optional, skip if redis package missing
    try:
        import redis as redis_lib

        r = redis_lib.Redis.from_url(getattr(settings, "CELERY_BROKER_URL", ""), socket_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except ImportError:
        pass  # redis package not installed — skip check
    except Exception:
        checks["redis"] = "error"

    all_ok = checks.get("database") == "ok"  # DB is the critical check
    checks["status"] = "healthy" if all_ok else "unhealthy"

    return JsonResponse(checks, status=200 if all_ok else 503)
