"""Billing views — Stripe Checkout, billing portal, and webhook handler."""

import logging

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from services.models import ServicePlan
from users.models import SubscriptionTier

from .models import Customer, PaymentEvent, Subscription, SubscriptionStatus

log = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


# ---------------------------------------------------------------------------
# Public / authenticated billing views
# ---------------------------------------------------------------------------


@login_required
def billing(request):
    """Show the user's current subscription status."""
    subscription = None
    try:
        customer = request.user.stripe_customer
        subscription = customer.subscriptions.filter(
            status__in=[
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIALING,
                SubscriptionStatus.PAST_DUE,
            ]
        ).first()
    except Customer.DoesNotExist:
        pass

    return render(request, "orders/billing.html", {"subscription": subscription})


@login_required
def create_checkout_session(request, plan_slug):
    """Start a Stripe Checkout session for the given plan."""
    plan = get_object_or_404(ServicePlan, slug=plan_slug, is_active=True)

    if not plan.stripe_price_id_monthly:
        messages.error(request, "This plan is not yet available for purchase. Please contact us.")
        return redirect("services:pricing")

    # Ensure a Stripe Customer record exists for this user
    customer, _ = Customer.objects.get_or_create(
        user=request.user,
        defaults={"stripe_customer_id": _get_or_create_stripe_customer(request.user)},
    )

    success_url = request.build_absolute_uri(reverse("orders:billing")) + "?checkout=success"
    cancel_url = request.build_absolute_uri(reverse("services:pricing"))

    try:
        session = stripe.checkout.Session.create(
            customer=customer.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": plan.stripe_price_id_monthly, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": str(request.user.pk), "plan_slug": plan_slug},
        )
    except stripe.error.StripeError as exc:
        log.exception("Stripe Checkout session creation failed: %s", exc)
        messages.error(request, "Could not start checkout. Please try again or contact support.")
        return redirect("services:pricing")

    return redirect(session.url, permanent=False)


@login_required
def billing_portal(request):
    """Open the Stripe Customer Portal so users can manage their subscription."""
    try:
        customer = request.user.stripe_customer
    except Customer.DoesNotExist:
        messages.info(request, "You don't have an active subscription yet.")
        return redirect("services:pricing")

    return_url = request.build_absolute_uri(reverse("orders:billing"))
    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=customer.stripe_customer_id,
            return_url=return_url,
        )
    except stripe.error.StripeError as exc:
        log.exception("Stripe billing portal session failed: %s", exc)
        messages.error(request, "Could not open billing portal. Please try again.")
        return redirect("orders:billing")

    return redirect(portal_session.url, permanent=False)


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

HANDLED_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Receive, verify, and process Stripe webhook events."""
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")

    # Idempotency — skip already-processed events
    if PaymentEvent.objects.filter(stripe_event_id=event["id"]).exists():
        return HttpResponse("already processed", status=200)

    if event["type"] in HANDLED_EVENTS:
        try:
            _handle_event(event)
        except Exception:  # noqa: BLE001
            log.exception("Webhook handler raised for event %s", event["id"])
            return HttpResponse("handler error", status=500)

    # Record event as processed
    try:
        PaymentEvent.objects.create(
            stripe_event_id=event["id"],
            event_type=event["type"],
            payload=dict(event),
        )
    except IntegrityError:
        pass  # race condition — another worker already recorded it

    return HttpResponse("ok", status=200)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_or_create_stripe_customer(user) -> str:
    """Create a Stripe Customer object and return its ID."""
    stripe_customer = stripe.Customer.create(
        email=user.email,
        name=user.full_name or user.email,
        metadata={"user_id": str(user.pk)},
    )
    return stripe_customer["id"]


def _handle_event(event: dict) -> None:
    """Route a Stripe event to the correct handler."""
    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data)
    elif event_type.startswith("customer.subscription."):
        _handle_subscription_change(data)


def _handle_checkout_completed(session: dict) -> None:
    """After a successful checkout, provision the subscription."""
    stripe_customer_id = session.get("customer")
    stripe_sub_id = session.get("subscription")
    if not stripe_customer_id or not stripe_sub_id:
        return

    try:
        customer = Customer.objects.get(stripe_customer_id=stripe_customer_id)
    except Customer.DoesNotExist:
        log.warning("Checkout completed for unknown customer %s", stripe_customer_id)
        return

    # Fetch full subscription from Stripe to get price/period data
    stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
    _upsert_subscription(customer, stripe_sub)

    # Upgrade the user's subscription_tier based on metadata
    plan_slug = session.get("metadata", {}).get("plan_slug", "")
    _update_user_tier(customer.user, plan_slug)


def _handle_subscription_change(subscription: dict) -> None:
    """Keep our Subscription record in sync with Stripe."""
    stripe_customer_id = subscription.get("customer")
    try:
        customer = Customer.objects.get(stripe_customer_id=stripe_customer_id)
    except Customer.DoesNotExist:
        return

    _upsert_subscription(customer, subscription)

    # Sync user tier — if canceled, downgrade to free
    new_status = subscription.get("status", "")
    if new_status in ("canceled", "unpaid", "incomplete_expired"):
        customer.user.subscription_tier = SubscriptionTier.FREE  # type: ignore[attr-defined]
        customer.user.save(update_fields=["subscription_tier"])


def _upsert_subscription(customer: Customer, stripe_sub: dict) -> Subscription:
    import datetime

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
    """Map a plan slug to a SubscriptionTier and save it on the user."""
    from services.models import ServicePlan

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
