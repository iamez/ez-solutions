"""
Multi-channel notification dispatch.

Supported channels:
  - email (default, always available)
  - telegram (requires TELEGRAM_BOT_TOKEN + user's chat_id)
  - signal (requires signal-cli-rest-api + user's phone number)

Each channel implements `send(recipient, subject, body, **kwargs)`.
Adding a new channel = subclass NotificationChannel + register in CHANNELS dict.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from django.conf import settings

log = logging.getLogger(__name__)


class NotificationChannel(ABC):
    """Base class for notification channels."""

    @abstractmethod
    def send(self, recipient: str, subject: str, body: str, **kwargs: Any) -> bool:
        """Send a notification. Returns True on success."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if this channel's settings are present and valid."""
        ...


class EmailChannel(NotificationChannel):
    """Email via Django's mail framework (always available)."""

    def send(self, recipient: str, subject: str, body: str, **kwargs: Any) -> bool:
        from django.core.mail import send_mail

        html_body = kwargs.get("html_body")
        if html_body:
            from django.core.mail import EmailMultiAlternatives

            msg = EmailMultiAlternatives(subject, body, None, [recipient])
            msg.attach_alternative(html_body, "text/html")
            return bool(msg.send(fail_silently=True))
        return bool(send_mail(subject, body, None, [recipient], fail_silently=True))

    def is_configured(self) -> bool:
        return True  # Django email backend is always available


class TelegramChannel(NotificationChannel):
    """
    Telegram Bot API notifications.

    Requires:
      - TELEGRAM_BOT_TOKEN in settings / env
      - recipient = Telegram chat_id (stored on User model or preferences)

    The bot must be created via @BotFather.
    Messages are sent via HTTPS (encrypted in transit).
    For additional E2E encryption, Telegram Secret Chats are user-initiated
    and not available via Bot API — so we rely on TLS transport encryption.
    """

    def send(self, recipient: str, subject: str, body: str, **kwargs: Any) -> bool:
        import httpx

        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        if not token:
            log.warning("TELEGRAM_BOT_TOKEN not set; skipping Telegram notification")
            return False

        import html as html_lib
        text = f"<b>{html_lib.escape(subject)}</b>\n\n{html_lib.escape(body)}"
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": recipient,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            resp = httpx.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except Exception:
            log.exception("Telegram send failed for chat_id=%s", recipient)
            return False

    def is_configured(self) -> bool:
        return bool(getattr(settings, "TELEGRAM_BOT_TOKEN", ""))


class SignalChannel(NotificationChannel):
    """
    Signal Messenger notifications via signal-cli-rest-api.

    Requires:
      - SIGNAL_CLI_REST_API_URL (e.g. http://localhost:8080)
      - SIGNAL_SENDER_NUMBER (registered Signal number, e.g. +1234567890)
      - recipient = phone number in E.164 format

    signal-cli-rest-api runs as a Docker container and exposes a REST API.
    Signal Protocol provides E2E encryption by default.
    See: https://github.com/bbernhard/signal-cli-rest-api
    """

    def send(self, recipient: str, subject: str, body: str, **kwargs: Any) -> bool:
        import httpx

        api_url = getattr(settings, "SIGNAL_CLI_REST_API_URL", "")
        sender = getattr(settings, "SIGNAL_SENDER_NUMBER", "")
        if not api_url or not sender:
            log.warning("Signal config incomplete; skipping Signal notification")
            return False

        message = f"{subject}\n\n{body}"
        url = f"{api_url.rstrip('/')}/v2/send"
        payload = {
            "message": message,
            "number": sender,
            "recipients": [recipient],
        }
        try:
            resp = httpx.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            return True
        except Exception:
            log.exception("Signal send failed for recipient=%s", recipient)
            return False

    def is_configured(self) -> bool:
        return bool(
            getattr(settings, "SIGNAL_CLI_REST_API_URL", "")
            and getattr(settings, "SIGNAL_SENDER_NUMBER", "")
        )


# Channel registry — add new channels here
CHANNELS: dict[str, NotificationChannel] = {
    "email": EmailChannel(),
    "telegram": TelegramChannel(),
    "signal": SignalChannel(),
}


def get_active_channels() -> dict[str, NotificationChannel]:
    """Return only channels that are currently configured."""
    return {name: ch for name, ch in CHANNELS.items() if ch.is_configured()}
