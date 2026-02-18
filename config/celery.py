from __future__ import annotations

import logging
import os

from celery import Celery
from celery.signals import task_failure, worker_ready, worker_shutdown

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("ez_solutions")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

_log = logging.getLogger("celery.failure")


@task_failure.connect
def handle_task_failure(
    task_id,
    exception,
    traceback,
    einfo,
    args,
    kwargs,
    **extra,
):
    """Permanent failure hook — fires after all retries are exhausted.

    Logs a structured ERROR so Sentry / log aggregators capture it, and
    sends an admin notification so operators are alerted immediately.
    """
    task_name = extra.get("sender", "unknown")
    _log.error(
        "PERMANENT TASK FAILURE | task=%s id=%s | %s: %s",
        task_name,
        task_id,
        type(exception).__name__,
        exception,
        exc_info=einfo,
    )

    # Best-effort admin alert — wrapped so a broken notification channel
    # never prevents the error from being logged.
    try:
        from notifications.tasks import send_admin_notification_task

        send_admin_notification_task.apply_async(
            kwargs={
                "subject": f"Task permanently failed: {task_name}",
                "body": (
                    f"Task {task_name} (id={task_id}) has exhausted all retries.\n\n"
                    f"Error: {type(exception).__name__}: {exception}\n\n"
                    f"Args: {args}\nKwargs: {kwargs}"
                ),
            },
            ignore_result=True,
        )
    except Exception:  # noqa: BLE001
        _log.exception("Could not send admin notification for failed task %s", task_id)


@worker_ready.connect
def on_worker_ready(**kwargs):
    _log.info("Celery worker ready")


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    _log.info("Celery worker shutting down")
