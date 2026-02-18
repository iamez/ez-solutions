from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from .emailing import send_checkout_success_email, send_subscription_canceled_email
from .models import PaymentEvent
from .webhooks import HANDLED_EVENTS, handle_event

log = logging.getLogger(__name__)
User = get_user_model()


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3, soft_time_limit=60, time_limit=120)
def process_stripe_event(payment_event_id: int) -> None:
    from django.utils import timezone

    from .models import EventStatus

    try:
        payment_event = PaymentEvent.objects.get(pk=payment_event_id)
    except PaymentEvent.DoesNotExist:
        log.warning("PaymentEvent %s disappeared before processing", payment_event_id)
        return

    if payment_event.event_type not in HANDLED_EVENTS:
        payment_event.status = EventStatus.SKIPPED
        payment_event.processed_at = timezone.now()
        payment_event.save(update_fields=["status", "processed_at"])
        return

    payment_event.status = EventStatus.PROCESSING
    payment_event.save(update_fields=["status"])

    try:
        handle_event(payment_event.payload)
        payment_event.status = EventStatus.PROCESSED
        payment_event.processed_at = timezone.now()
        payment_event.save(update_fields=["status", "processed_at"])
    except Exception as exc:
        payment_event.status = EventStatus.FAILED
        payment_event.error_message = str(exc)[:2000]
        payment_event.processed_at = timezone.now()
        payment_event.save(update_fields=["status", "error_message", "processed_at"])
        log.exception(
            "Async webhook handler failed for event %s", payment_event.stripe_event_id
        )
        raise


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3, soft_time_limit=60, time_limit=120)
def send_checkout_success_email_task(user_id: int, plan_name: str) -> None:
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        log.warning("User %s not found for checkout email", user_id)
        return

    send_checkout_success_email(
        user_email=user.email,
        first_name=user.first_name,
        plan_name=plan_name,
    )


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3, soft_time_limit=60, time_limit=120)
def send_subscription_canceled_email_task(user_id: int) -> None:
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        log.warning("User %s not found for canceled email", user_id)
        return

    send_subscription_canceled_email(
        user_email=user.email,
        first_name=user.first_name,
    )


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3, soft_time_limit=60, time_limit=120)
def send_welcome_email_task(user_id: int) -> None:
    from .emailing import send_welcome_email

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        log.warning("User %s not found for welcome email", user_id)
        return

    send_welcome_email(
        user_email=user.email,
        first_name=user.first_name,
    )


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3, soft_time_limit=60, time_limit=120)
def send_ticket_notification_task(ticket_id: int, message_id: int, recipient_email: str) -> None:
    from tickets.models import TicketMessage

    from .emailing import send_ticket_notification_email

    try:
        message = TicketMessage.objects.select_related("ticket").get(pk=message_id)
    except TicketMessage.DoesNotExist:
        log.warning("TicketMessage %s not found for notification", message_id)
        return

    send_ticket_notification_email(
        recipient_email=recipient_email,
        ticket_subject=message.ticket.subject,
        message_body=message.body[:500],
        ticket_id=ticket_id,
    )
