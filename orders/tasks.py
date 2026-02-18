from __future__ import annotations

import logging

from celery import shared_task

from .models import PaymentEvent
from .webhooks import HANDLED_EVENTS, handle_event

log = logging.getLogger(__name__)


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
