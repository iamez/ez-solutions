import logging

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from services.models import ServicePlan

from .models import Customer, Order, PaymentEvent, SubscriptionStatus
from .tasks import process_stripe_event
from .webhooks import HANDLED_EVENTS, handle_event

log = logging.getLogger(__name__)


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
def order_history(request):
    """Show the user's order history, paginated."""
    orders = Order.objects.none()
    try:
        customer = request.user.stripe_customer
        orders = customer.orders.select_related("service_plan").order_by("-created_at")
    except Customer.DoesNotExist:
        pass

    paginator = Paginator(orders, 15)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "orders/order_history.html", {"orders": page})


@login_required
@require_POST
def create_checkout_session(request, plan_slug):
    """Start a Stripe Checkout session for the given plan."""
    plan = get_object_or_404(ServicePlan, slug=plan_slug, is_active=True)

    if not plan.stripe_price_id_monthly:
        messages.error(request, "This plan is not yet available for purchase. Please contact us.")
        return redirect("services:pricing")

    # Ensure a Stripe Customer record exists for this user
    try:
        customer = Customer.objects.get(user=request.user)
    except Customer.DoesNotExist:
        with transaction.atomic():
            stripe_id = _get_or_create_stripe_customer(request.user)
            customer = Customer.objects.create(
                user=request.user,
                stripe_customer_id=stripe_id,
            )

    success_url = request.build_absolute_uri(reverse("orders:billing")) + "?checkout=success"
    cancel_url = request.build_absolute_uri(reverse("services:pricing"))

    try:
        session = stripe.checkout.Session.create(
            api_key=settings.STRIPE_SECRET_KEY,
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
@require_POST
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
            api_key=settings.STRIPE_SECRET_KEY,
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


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Receive, verify, and enqueue Stripe webhook events."""
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")

    created = False
    try:
        payment_event, created = PaymentEvent.objects.get_or_create(
            stripe_event_id=event["id"],
            defaults={
                "event_type": event["type"],
                "payload": dict(event),
            },
        )
    except IntegrityError:
        return HttpResponse("already processed", status=200)

    if created and payment_event.event_type in HANDLED_EVENTS:
        try:
            process_stripe_event.apply_async(args=[payment_event.pk], ignore_result=True)
        except Exception:  # noqa: BLE001
            log.exception(
                "Celery enqueue failed for %s; processing synchronously",
                payment_event.stripe_event_id,
            )
            handle_event(payment_event.payload)

    return HttpResponse("ok", status=200)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_or_create_stripe_customer(user) -> str:
    """Create a Stripe Customer object and return its ID."""
    stripe_customer = stripe.Customer.create(
        api_key=settings.STRIPE_SECRET_KEY,
        email=user.email,
        name=user.full_name or user.email,
        metadata={"user_id": str(user.pk)},
    )
    return stripe_customer["id"]
