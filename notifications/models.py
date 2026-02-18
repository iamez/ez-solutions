"""Notification preference and delivery log models."""

from django.conf import settings
from django.db import models


class NotificationPreference(models.Model):
    """Per-user channel preferences and contact identifiers for Telegram/Signal."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_prefs",
    )

    # Channel toggles — which channels does the user want?
    email_enabled = models.BooleanField(default=True)
    telegram_enabled = models.BooleanField(default=False)
    signal_enabled = models.BooleanField(default=False)

    # Contact identifiers (stored encrypted-at-rest in prod via DB-level encryption)
    telegram_chat_id = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Telegram chat ID obtained after user starts the bot",
    )
    signal_phone = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Phone number in E.164 format (e.g., +1234567890)",
    )

    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

    def __str__(self) -> str:
        channels = []
        if self.email_enabled:
            channels.append("email")
        if self.telegram_enabled:
            channels.append("telegram")
        if self.signal_enabled:
            channels.append("signal")
        return f"{self.user.email}: {', '.join(channels) or 'none'}"

    def active_channels(self) -> list[str]:
        """Return list of channel names the user has enabled AND has credentials for."""
        channels = []
        if self.email_enabled:
            channels.append("email")
        if self.telegram_enabled and self.telegram_chat_id:
            channels.append("telegram")
        if self.signal_enabled and self.signal_phone:
            channels.append("signal")
        return channels


class NotificationLog(models.Model):
    """Audit trail for every notification sent."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_logs",
        null=True,
        blank=True,
    )
    channel = models.CharField(max_length=20)
    subject = models.CharField(max_length=255)
    recipient = models.CharField(max_length=255)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"{status} [{self.channel}] {self.subject[:50]}"
