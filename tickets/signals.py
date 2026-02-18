"""Signal handlers for ticket email notifications."""

from __future__ import annotations

import logging

from django.db.models.signals import post_save

log = logging.getLogger(__name__)


def connect_signals():
    """Connect ticket notification signals. Called from TicketsConfig.ready()."""
    from .models import TicketMessage

    post_save.connect(on_ticket_message_created, sender=TicketMessage)


def on_ticket_message_created(sender, instance, created, **kwargs):
    """Notify the other party when a ticket message is created."""
    if not created:
        return

    from orders.tasks import send_ticket_notification_task

    ticket = instance.ticket
    # If staff replied → notify customer. If customer replied → notify staff (admin email).
    if instance.is_staff_reply:
        recipient_email = ticket.user.email
    else:
        # Notify admin/staff about customer reply
        from django.conf import settings

        recipient_email = settings.DEFAULT_FROM_EMAIL

    try:
        send_ticket_notification_task.apply_async(
            args=[ticket.pk, instance.pk, recipient_email],
            ignore_result=True,
        )
    except Exception:  # noqa: BLE001
        log.exception("Failed to enqueue ticket notification for ticket %s", ticket.pk)
