"""Development settings."""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]  # noqa: S104  # nosec B104

# Use simple static storage in dev — no need to run collectstatic
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Django debug toolbar
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]

# Console email backend — no SMTP needed in dev
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# SQLite is fine for local development
# To use Postgres locally: set DB_ENGINE + DB_NAME + DB_USER + DB_PASSWORD in .env

# CORS — allow all origins in dev only
CORS_ALLOW_ALL_ORIGINS = True
