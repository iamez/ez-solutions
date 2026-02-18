"""Celery tasks for multi-channel notification dispatch."""

from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

log = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
)
def send_notification_task(
    user_id: int,
    subject: str,
    body: str,
    html_body: str = "",
    channels: list[str] | None = None,
) -> dict[str, bool]:
    """Send a multi-channel notification to a user."""
    from notifications.dispatch import notify_user

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        log.warning("User %s not found for notification", user_id)
        return {}

    return notify_user(
        user=user,
        subject=subject,
        body=body,
        html_body=html_body,
        channels=channels,
    )


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
)
def send_admin_notification_task(
    subject: str,
    body: str,
    html_body: str = "",
) -> dict[str, bool]:
    """Send a multi-channel notification to site admins."""
    from notifications.dispatch import notify_admin

    return notify_admin(
        subject=subject,
        body=body,
        html_body=html_body,
    )
