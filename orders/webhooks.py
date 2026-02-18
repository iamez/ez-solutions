from __future__ import annotations

import datetime
import logging

import stripe

from services.models import ServicePlan
from users.models import SubscriptionTier

from .models import Customer, Subscription

log = logging.getLogger(__name__)

HANDLED_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}


def handle_event(event: dict) -> None:
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data)
    elif event_type.startswith("customer.subscription."):
        _handle_subscription_change(data)


def _handle_checkout_completed(session: dict) -> None:
    stripe_customer_id = session.get("customer")
    stripe_sub_id = session.get("subscription")
    if not stripe_customer_id or not stripe_sub_id:
        return

    try:
        customer = Customer.objects.get(stripe_customer_id=stripe_customer_id)
    except Customer.DoesNotExist:
        log.warning("Checkout completed for unknown customer %s", stripe_customer_id)
        return

    stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
    _upsert_subscription(customer, stripe_sub)

    plan_slug = session.get("metadata", {}).get("plan_slug", "")
    _update_user_tier(customer.user, plan_slug)
    _queue_checkout_success_email(customer.user.pk, _resolve_plan_name(plan_slug))


def _handle_subscription_change(subscription: dict) -> None:
    stripe_customer_id = subscription.get("customer")
    try:
        customer = Customer.objects.get(stripe_customer_id=stripe_customer_id)
    except Customer.DoesNotExist:
        return

    existing = Subscription.objects.filter(
        stripe_subscription_id=subscription.get("id", ""),
    ).first()
    previous_status = existing.status if existing else ""
    _upsert_subscription(customer, subscription)

    new_status = subscription.get("status", "")
    if new_status in ("canceled", "unpaid", "incomplete_expired"):
        customer.user.subscription_tier = SubscriptionTier.FREE  # type: ignore[attr-defined]
        customer.user.save(update_fields=["subscription_tier"])
        if previous_status != new_status:
            _queue_subscription_canceled_email(customer.user.pk)


def _upsert_subscription(customer: Customer, stripe_sub: dict) -> Subscription:
    def _ts(val):
        if val:
            return datetime.datetime.fromtimestamp(val, tz=datetime.UTC)
        return None

    price_id = ""
    items = stripe_sub.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id", "")

    sub, _ = Subscription.objects.update_or_create(
        stripe_subscription_id=stripe_sub["id"],
        defaults={
            "customer": customer,
            "stripe_price_id": price_id,
            "status": stripe_sub.get("status", "incomplete"),
            "current_period_start": _ts(stripe_sub.get("current_period_start")),
            "current_period_end": _ts(stripe_sub.get("current_period_end")),
            "cancel_at_period_end": stripe_sub.get("cancel_at_period_end", False),
        },
    )
    return sub


def _update_user_tier(user, plan_slug: str) -> None:
    try:
        plan = ServicePlan.objects.get(slug=plan_slug)
        tier_key = plan.tier_key
    except ServicePlan.DoesNotExist:
        tier_key = ""

    mapping = {
        "starter": SubscriptionTier.STARTER,
        "professional": SubscriptionTier.PROFESSIONAL,
        "enterprise": SubscriptionTier.ENTERPRISE,
    }
    new_tier = mapping.get(tier_key)
    if new_tier:
        user.subscription_tier = new_tier
        user.save(update_fields=["subscription_tier"])


def _resolve_plan_name(plan_slug: str) -> str:
    if not plan_slug:
        return "Your selected plan"
    try:
        plan = ServicePlan.objects.get(slug=plan_slug)
        return plan.name
    except ServicePlan.DoesNotExist:
        return plan_slug.replace("-", " ").title()


def _queue_checkout_success_email(user_id: int, plan_name: str) -> None:
    from .tasks import send_checkout_success_email_task

    try:
        send_checkout_success_email_task.apply_async(args=[user_id, plan_name], ignore_result=True)
    except Exception:  # noqa: BLE001
        log.exception("Email enqueue failed for user %s; sending synchronously", user_id)
        send_checkout_success_email_task.run(user_id, plan_name)


def _queue_subscription_canceled_email(user_id: int) -> None:
    from .tasks import send_subscription_canceled_email_task

    try:
        send_subscription_canceled_email_task.apply_async(args=[user_id], ignore_result=True)
    except Exception:  # noqa: BLE001
        log.exception("Cancel email enqueue failed for user %s; sending synchronously", user_id)
        send_subscription_canceled_email_task.run(user_id)
