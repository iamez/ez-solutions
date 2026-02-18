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

# Sentry
try:
    if SENTRY_DSN:  # noqa: F405
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,  # noqa: F405
            integrations=[DjangoIntegration()],
            traces_sample_rate=0.2,
            send_default_pii=False,
        )
except (ImportError, Exception):  # noqa: BLE001
    pass  # sentry-sdk not installed or config error
