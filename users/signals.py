"""Signal handlers for email notifications."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def connect_signals():
    """Import allauth signals and connect handlers. Called from UsersConfig.ready()."""
    from allauth.account.signals import user_signed_up

    user_signed_up.connect(on_user_signed_up)


def on_user_signed_up(sender, request, user, **kwargs):
    """Send a welcome email when a new user registers."""
    from orders.tasks import send_welcome_email_task

    try:
        send_welcome_email_task.apply_async(args=[user.pk], ignore_result=True)
    except Exception:  # noqa: BLE001
        log.exception("Failed to enqueue welcome email for user %s", user.pk)
        # Fallback: run synchronously
        send_welcome_email_task.run(user.pk)

    # Notify admins about new signup via all configured channels
    _notify_admin_new_signup(user)


def _notify_admin_new_signup(user) -> None:
    from notifications.tasks import send_admin_notification_task

    try:
        send_admin_notification_task.apply_async(
            args=[
                "New user signup",
                f"New user registered: {user.email} (ID: {user.pk}).",
            ],
            kwargs={
                "html_body": (
                    f"<p>New user registered: <strong>{user.email}</strong> (ID: {user.pk}).</p>"
                ),
            },
            ignore_result=True,
        )
    except Exception:  # noqa: BLE001
        log.exception("Failed to enqueue admin signup notification for user %s", user.pk)
