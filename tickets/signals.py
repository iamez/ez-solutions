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

        recipient_email = settings.SUPPORT_EMAIL

    try:
        send_ticket_notification_task.apply_async(
            args=[ticket.pk, instance.pk, recipient_email],
            ignore_result=True,
        )
    except Exception:  # noqa: BLE001
        log.exception("Failed to enqueue ticket notification for ticket %s", ticket.pk)

    # Multi-channel dispatch for ticket replies
    _queue_ticket_multichannel(instance, ticket, recipient_email)


def _queue_ticket_multichannel(message, ticket, recipient_email: str) -> None:
    from notifications.tasks import send_admin_notification_task, send_notification_task

    subject = f"Ticket #{ticket.pk}: {ticket.subject}"
    body = f"New reply on ticket #{ticket.pk}:\n\n{message.body[:500]}"
    html_body = (
        f"<p>New reply on ticket <strong>#{ticket.pk}</strong>:</p><p>{message.body[:500]}</p>"
    )

    if message.is_staff_reply:
        # Staff replied → notify customer via all their channels
        try:
            send_notification_task.apply_async(
                args=[ticket.user.pk, subject, body],
                kwargs={"html_body": html_body},
                ignore_result=True,
            )
        except Exception:  # noqa: BLE001
            log.exception("Multi-channel ticket notification failed for user %s", ticket.user.pk)
    else:
        # Customer replied → notify admins via all admin channels
        try:
            send_admin_notification_task.apply_async(
                args=[subject, body],
                kwargs={"html_body": html_body},
                ignore_result=True,
            )
        except Exception:  # noqa: BLE001
            log.exception("Multi-channel admin ticket notification failed for ticket %s", ticket.pk)
