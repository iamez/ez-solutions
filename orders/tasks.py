from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from .emailing import send_checkout_success_email, send_subscription_canceled_email
from .models import PaymentEvent
from .webhooks import HANDLED_EVENTS, handle_event

log = logging.getLogger(__name__)
User = get_user_model()


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_stripe_event(payment_event_id: int) -> None:
    try:
        payment_event = PaymentEvent.objects.get(pk=payment_event_id)
    except PaymentEvent.DoesNotExist:
        log.warning("PaymentEvent %s disappeared before processing", payment_event_id)
        return

    if payment_event.event_type not in HANDLED_EVENTS:
        return

    try:
        handle_event(payment_event.payload)
    except Exception:
        log.exception(
            "Async webhook handler failed for event %s", payment_event.stripe_event_id
        )
        raise


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
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


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
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
