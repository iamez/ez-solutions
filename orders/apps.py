from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(_setup_periodic_tasks, sender=self)


def _setup_periodic_tasks(sender, **kwargs):
    """Ensure Celery Beat periodic tasks are registered after every migration run.

    Safe to call multiple times — uses update_or_create so it is idempotent.
    Skips gracefully when the django_celery_beat tables do not yet exist (e.g.
    during the very first `migrate` before the beat app is applied).
    """
    try:
        from django.core.management import call_command

        call_command("setup_periodic_tasks", verbosity=0)
    except Exception:  # noqa: BLE001
        # Tables may not exist yet on a fresh database — silently skip.
        pass
