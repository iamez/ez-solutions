"""
High-level notification dispatch.

Usage:
    from notifications.dispatch import notify_user

    notify_user(
        user=user,
        subject="Your VPS is ready",
        body="Your server 10.0.0.5 is online.",
        html_body="<p>Your server <strong>10.0.0.5</strong> is online.</p>",
        channels=["email", "telegram"],  # optional; defaults to user prefs
    )
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from .channels import CHANNELS, get_active_channels

log = logging.getLogger(__name__)


def notify_user(
    user,
    subject: str,
    body: str,
    html_body: str = "",
    channels: list[str] | None = None,
) -> dict[str, bool]:
    """
    Send a notification to a user across one or more channels.

    Args:
        user: Django User instance (must have .email; optionally .telegram_chat_id, .signal_phone)
        subject: Notification subject / title
        body: Plain-text body
        html_body: Optional HTML body (used by email channel)
        channels: Channel names to use. If None, uses all configured channels
                  the user has contact info for.

    Returns:
        Dict mapping channel name → success bool.
    """
    active = get_active_channels()
    results: dict[str, bool] = {}

    if channels is None:
        prefs = getattr(user, "notification_prefs", None)
        channels = prefs.active_channels() if prefs else ["email"]

    for name in channels:
        channel = active.get(name)
        if not channel:
            log.debug("Channel '%s' not configured; skipping", name)
            continue

        recipient = _get_recipient(user, name)
        if not recipient:
            log.debug("No %s contact for user %s; skipping", name, user.pk)
            continue

        try:
            ok = channel.send(recipient, subject, body, html_body=html_body)
            results[name] = ok
            _log_notification(user=user, channel=name, subject=subject, recipient=recipient, success=ok)
        except Exception as exc:
            log.exception("Channel '%s' failed for user %s", name, user.pk)
            results[name] = False
            _log_notification(user=user, channel=name, subject=subject, recipient=recipient, success=False, error=str(exc))

    return results


def notify_admin(
    subject: str,
    body: str,
    html_body: str = "",
) -> dict[str, bool]:
    """Send a notification to the site admin(s) via configured channels."""
    admin_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")
    admin_telegram = getattr(settings, "ADMIN_TELEGRAM_CHAT_ID", "")
    admin_signal = getattr(settings, "ADMIN_SIGNAL_NUMBER", "")
    active = get_active_channels()
    results: dict[str, bool] = {}

    targets = {
        "email": admin_email,
        "telegram": admin_telegram,
        "signal": admin_signal,
    }

    for name, recipient in targets.items():
        if not recipient or name not in active:
            continue
        try:
            ok = active[name].send(recipient, subject, body, html_body=html_body)
            results[name] = ok
            _log_notification(user=None, channel=name, subject=subject, recipient=recipient, success=ok)
        except Exception as exc:
            log.exception("Admin channel '%s' failed", name)
            results[name] = False
            _log_notification(user=None, channel=name, subject=subject, recipient=recipient, success=False, error=str(exc))

    return results


def _get_recipient(user, channel_name: str) -> str:
    """Extract the appropriate contact identifier for the given channel."""
    if channel_name == "email":
        return user.email
    prefs = getattr(user, "notification_prefs", None)
    if prefs is None:
        return ""
    if channel_name == "telegram":
        return prefs.telegram_chat_id or ""
    if channel_name == "signal":
        return prefs.signal_phone or ""
    return ""


def _log_notification(
    user, channel: str, subject: str, recipient: str, success: bool, error: str = ""
) -> None:
    """Write a NotificationLog entry (fire-and-forget; never raise)."""
    try:
        from .models import NotificationLog
        NotificationLog.objects.create(
            user=user,
            channel=channel,
            subject=subject[:255],
            recipient=recipient[:255],
            success=success,
            error_message=error[:2000] if error else "",
        )
    except Exception:
        log.debug("Failed to write NotificationLog", exc_info=True)
