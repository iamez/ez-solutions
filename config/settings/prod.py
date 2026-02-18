"""Production settings — security hardened."""

from .base import *  # noqa: F401, F403

DEBUG = False

# Security headers
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"

# Enforce CSP in production (report-only is only for dev)
CSP_REPORT_ONLY = False

# Require email verification in production
ACCOUNT_EMAIL_VERIFICATION = "mandatory"

# Session security
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True  # sliding window

# CSRF trusted origins (add your real domain(s) here)
CSRF_TRUSTED_ORIGINS = config(  # noqa: F405
    "CSRF_TRUSTED_ORIGINS",
    default="https://ez-solutions.com,https://www.ez-solutions.com",
    cast=Csv(),  # noqa: F405
)

# Email via Anymail (Mailgun by default; configure MAILGUN_API_KEY in env)
EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
ANYMAIL = {
    "MAILGUN_API_KEY": config("MAILGUN_API_KEY", default=""),  # noqa: F405
    "MAILGUN_SENDER_DOMAIN": config("MAILGUN_SENDER_DOMAIN", default=""),  # noqa: F405
}

# CORS — restrict to known origins in prod
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="", cast=Csv())  # noqa: F405

# ---------------------------------------------------------------------------
# Celery — production overrides
# Redis URL must be set via REDIS_URL env var in production.
# Use rediss:// (TLS) when your provider supports it, e.g.:
#   REDIS_URL=rediss://:password@your-redis-host:6380/0
# ---------------------------------------------------------------------------
_redis_url = config("REDIS_URL", default="redis://localhost:6379/0")  # noqa: F405

CELERY_BROKER_URL = _redis_url
CELERY_RESULT_BACKEND = _redis_url

# Must be >= the longest task time_limit (provision_vps_task = 300 s)
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": 3600,
    "max_retries": 5,
}

# Sentry
try:
    if SENTRY_DSN:  # noqa: F405
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,  # noqa: F405
            integrations=[DjangoIntegration(), CeleryIntegration()],
            traces_sample_rate=0.2,
            send_default_pii=False,
        )
except ImportError:
    pass  # sentry-sdk not installed — optional dependency
except Exception as _sentry_exc:  # noqa: BLE001
    import logging as _logging

    _logging.getLogger("config.settings.prod").warning(
        "Sentry initialization failed: %s", _sentry_exc
    )
