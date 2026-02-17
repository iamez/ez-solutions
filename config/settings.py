# This file is superseded by the config/settings/ package.
# Set DJANGO_SETTINGS_MODULE=config.settings.dev  (development)
#                          or config.settings.prod (production)
# manage.py defaults to config.settings.dev when not set.
raise ImportError(
    "Do not import config.settings directly. "
    "Use config.settings.dev or config.settings.prod via DJANGO_SETTINGS_MODULE."
)
