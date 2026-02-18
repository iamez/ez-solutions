from __future__ import annotations

import datetime
import logging
from decimal import Decimal

import stripe

from services.models import ServicePlan
from users.models import SubscriptionTier

from .models import Customer, Order, OrderStatus, ProvisioningJob, Subscription

log = logging.getLogger(__name__)

HANDLED_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
}


def handle_event(event: dict) -> None:
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data)
    elif event_type.startswith("customer.subscription."):
        _handle_subscription_change(data)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(data)


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
    sub = _upsert_subscription(customer, stripe_sub)

    plan_slug = session.get("metadata", {}).get("plan_slug", "")
    plan = _get_plan(plan_slug)
    _update_user_tier(customer.user, plan)

    # Create Order record
    order = None
    if plan:
        amount_cents = session.get("amount_total") or 0
        order = Order.objects.create(
            customer=customer,
            service_plan=plan,
            subscription=sub,
            status=OrderStatus.PAID,
            stripe_checkout_session_id=session.get("id", ""),
            stripe_payment_intent_id=session.get("payment_intent", ""),
            amount_total=Decimal(amount_cents) / Decimal("100"),
            currency=session.get("currency", "usd"),
            metadata=session.get("metadata", {}),
        )

    # Queue VPS provisioning for paid plans with a tier
    if order and plan and plan.tier_key:
        _queue_provisioning(order)

    plan_name = plan.name if plan else plan_slug.replace("-", " ").title() or "Your selected plan"
    _queue_checkout_success_email(customer.user.pk, plan_name)


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
    sub = _upsert_subscription(customer, subscription)

    new_status = subscription.get("status", "")
    if new_status in ("active", "trialing"):
        _sync_tier_from_price(customer.user, sub.stripe_price_id)
    elif new_status in ("canceled", "unpaid", "incomplete_expired"):
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


def _get_plan(plan_slug: str):
    """Fetch ServicePlan by slug, returning None if not found."""
    if not plan_slug:
        return None
    try:
        return ServicePlan.objects.get(slug=plan_slug)
    except ServicePlan.DoesNotExist:
        return None


def _update_user_tier(user, plan) -> None:
    tier_key = plan.tier_key if plan else ""

    mapping = {
        "starter": SubscriptionTier.STARTER,
        "professional": SubscriptionTier.PROFESSIONAL,
        "enterprise": SubscriptionTier.ENTERPRISE,
    }
    new_tier = mapping.get(tier_key)
    if new_tier:
        user.subscription_tier = new_tier
        user.save(update_fields=["subscription_tier"])


def _sync_tier_from_price(user, stripe_price_id: str) -> None:
    """Look up a ServicePlan by its Stripe price ID and update the user tier."""
    if not stripe_price_id:
        return
    plan = (
        ServicePlan.objects.filter(stripe_price_id_monthly=stripe_price_id).first()
        or ServicePlan.objects.filter(stripe_price_id_annual=stripe_price_id).first()
    )
    _update_user_tier(user, plan)


def _queue_provisioning(order: Order) -> None:
    """Create a ProvisioningJob and dispatch the async task."""
    from .tasks import provision_vps_task

    job = ProvisioningJob.objects.create(
        order=order,
        provider="demo",
        payload={
            "plan_slug": order.service_plan.slug,
            "tier_key": order.service_plan.tier_key,
        },
    )
    try:
        provision_vps_task.apply_async(args=[job.pk], ignore_result=True)
    except Exception:  # noqa: BLE001
        log.exception("Provisioning task enqueue failed for job %s; running synchronously", job.pk)
        provision_vps_task.run(job.pk)


def _queue_checkout_success_email(user_id: int, plan_name: str) -> None:
    from .tasks import send_checkout_success_email_task

    try:
        send_checkout_success_email_task.apply_async(args=[user_id, plan_name], ignore_result=True)
    except Exception:  # noqa: BLE001
        log.exception("Email enqueue failed for user %s; sending synchronously", user_id)
        send_checkout_success_email_task.run(user_id, plan_name)

    # Multi-channel dispatch (email + telegram + signal)
    _queue_checkout_notifications(user_id, plan_name)


def _queue_checkout_notifications(user_id: int, plan_name: str) -> None:
    from notifications.tasks import (
        send_admin_notification_task,
        send_notification_task,
    )

    user_body = f"Your {plan_name} plan is now active. Thank you for subscribing!"
    user_html = (
        f"<p>Your <strong>{plan_name}</strong> plan is now active. Thank you for subscribing!</p>"
    )
    try:
        send_notification_task.apply_async(
            args=[user_id, "Subscription activated", user_body],
            kwargs={"html_body": user_html},
            ignore_result=True,
        )
    except Exception:  # noqa: BLE001
        log.exception(
            "Multi-channel user notification failed for checkout user %s",
            user_id,
        )

    admin_body = f"User {user_id} subscribed to {plan_name}."
    admin_html = (
        f"<p>User <strong>{user_id}</strong> subscribed to <strong>{plan_name}</strong>.</p>"
    )
    try:
        send_admin_notification_task.apply_async(
            args=["New subscription", admin_body],
            kwargs={"html_body": admin_html},
            ignore_result=True,
        )
    except Exception:  # noqa: BLE001
        log.exception(
            "Multi-channel admin notification failed for checkout user %s",
            user_id,
        )


def _queue_subscription_canceled_email(user_id: int) -> None:
    from .tasks import send_subscription_canceled_email_task

    try:
        send_subscription_canceled_email_task.apply_async(args=[user_id], ignore_result=True)
    except Exception:  # noqa: BLE001
        log.exception("Cancel email enqueue failed for user %s; sending synchronously", user_id)
        send_subscription_canceled_email_task.run(user_id)

    # Multi-channel dispatch (email + telegram + signal)
    _queue_cancellation_notifications(user_id)


def _queue_cancellation_notifications(user_id: int) -> None:
    from notifications.tasks import (
        send_admin_notification_task,
        send_notification_task,
    )

    user_body = "Your subscription has been canceled. You can resubscribe at any time."
    user_html = "<p>Your subscription has been canceled. You can resubscribe at any time.</p>"
    try:
        send_notification_task.apply_async(
            args=[user_id, "Subscription canceled", user_body],
            kwargs={"html_body": user_html},
            ignore_result=True,
        )
    except Exception:  # noqa: BLE001
        log.exception(
            "Multi-channel user notification failed for cancellation user %s",
            user_id,
        )

    admin_body = f"User {user_id} has canceled their subscription."
    admin_html = f"<p>User <strong>{user_id}</strong> has canceled their subscription.</p>"
    try:
        send_admin_notification_task.apply_async(
            args=["Subscription canceled", admin_body],
            kwargs={"html_body": admin_html},
            ignore_result=True,
        )
    except Exception:  # noqa: BLE001
        log.exception(
            "Multi-channel admin notification failed for cancellation user %s",
            user_id,
        )


def _handle_payment_failed(invoice: dict) -> None:
    """Handle invoice.payment_failed — notify user of failed recurring payment."""
    stripe_customer_id = invoice.get("customer")
    if not stripe_customer_id:
        return

    try:
        customer = Customer.objects.get(stripe_customer_id=stripe_customer_id)
    except Customer.DoesNotExist:
        log.warning("Payment failed for unknown customer %s", stripe_customer_id)
        return

    amount_cents = invoice.get("amount_due") or 0
    amount = str(Decimal(amount_cents) / Decimal("100"))
    currency = invoice.get("currency", "usd")

    _queue_payment_failed_email(customer.user.pk, amount, currency)


def _queue_payment_failed_email(user_id: int, amount: str, currency: str) -> None:
    from .tasks import send_payment_failed_email_task

    try:
        send_payment_failed_email_task.apply_async(
            args=[user_id, amount, currency], ignore_result=True
        )
    except Exception:  # noqa: BLE001
        log.exception(
            "Payment-failed email enqueue failed for user %s; sending synchronously",
            user_id,
        )
        send_payment_failed_email_task.run(user_id, amount, currency)

    # Multi-channel dispatch (email + telegram + signal)
    _queue_payment_failed_notifications(user_id, amount, currency)


def _queue_payment_failed_notifications(user_id: int, amount: str, currency: str) -> None:
    from notifications.tasks import (
        send_admin_notification_task,
        send_notification_task,
    )

    user_body = (
        f"Your payment of {amount} {currency.upper()} failed. "
        "Please update your payment method to avoid service interruption."
    )
    user_html = (
        f"<p>Your payment of <strong>{amount} {currency.upper()}</strong> failed. "
        "Please update your payment method to avoid service interruption.</p>"
    )
    try:
        send_notification_task.apply_async(
            args=[user_id, "Payment failed", user_body],
            kwargs={"html_body": user_html},
            ignore_result=True,
        )
    except Exception:  # noqa: BLE001
        log.exception(
            "Multi-channel user notification failed for payment-failed user %s",
            user_id,
        )

    admin_body = f"User {user_id} payment of {amount} {currency.upper()} failed."
    admin_html = (
        f"<p>User <strong>{user_id}</strong> payment of "
        f"<strong>{amount} {currency.upper()}</strong> failed.</p>"
    )
    try:
        send_admin_notification_task.apply_async(
            args=["Payment failed", admin_body],
            kwargs={"html_body": admin_html},
            ignore_result=True,
        )
    except Exception:  # noqa: BLE001
        log.exception(
            "Multi-channel admin notification failed for payment-failed user %s",
            user_id,
        )
