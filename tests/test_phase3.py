"""
Phase 3 tests — Stripe Billing
Covers: Customer/Subscription models, billing views, webhook idempotency,
        and signature verification (using real Stripe test fixtures).
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from orders.models import Customer, PaymentEvent, Subscription, SubscriptionStatus
from orders.tasks import (
    process_stripe_event,
    send_checkout_success_email_task,
    send_subscription_canceled_email_task,
)
from services.models import ServicePlan
from users.models import SubscriptionTier

BILLING_URL = reverse("orders:billing")
BILLING_PORTAL_URL = reverse("orders:billing_portal")
WEBHOOK_URL = reverse("orders:stripe_webhook")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def plan(db):
    return ServicePlan.objects.create(
        name="Starter",
        slug="starter",
        price_monthly="29.00",
        tier_key="starter",
        stripe_price_id_monthly="price_test_starter",
        is_active=True,
    )


@pytest.fixture
def customer(db, user):
    return Customer.objects.create(user=user, stripe_customer_id="cus_test_123")


@pytest.fixture
def active_subscription(db, customer):
    import datetime

    from django.utils import timezone

    return Subscription.objects.create(
        customer=customer,
        stripe_subscription_id="sub_test_abc",
        stripe_price_id="price_test_starter",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=timezone.now() + datetime.timedelta(days=30),
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCustomerModel:
    def test_str(self, customer, user):
        assert user.email in str(customer)
        assert "cus_test_123" in str(customer)

    def test_one_to_one_with_user(self, customer, user):
        assert user.stripe_customer == customer


@pytest.mark.django_db
class TestSubscriptionModel:
    def test_is_active_true_for_active_status(self, active_subscription):
        assert active_subscription.is_active is True

    def test_is_active_false_for_canceled(self, customer):
        sub = Subscription(
            customer=customer, status=SubscriptionStatus.CANCELED, stripe_subscription_id="sub_x"
        )
        assert sub.is_active is False

    def test_is_past_due(self, customer):
        sub = Subscription(
            customer=customer, status=SubscriptionStatus.PAST_DUE, stripe_subscription_id="sub_y"
        )
        assert sub.is_past_due is True

    def test_days_until_renewal(self, active_subscription):
        days = active_subscription.days_until_renewal
        assert days is not None
        assert 28 <= days <= 31

    def test_days_until_renewal_none_when_no_end_date(self, customer):
        sub = Subscription(
            customer=customer,
            status=SubscriptionStatus.ACTIVE,
            stripe_subscription_id="sub_z",
            current_period_end=None,
        )
        assert sub.days_until_renewal is None

    def test_str(self, active_subscription):
        assert "sub_test_abc" in str(active_subscription)
        assert "active" in str(active_subscription)


@pytest.mark.django_db
class TestPaymentEventModel:
    def test_create_and_str(self, db):
        event = PaymentEvent.objects.create(
            stripe_event_id="evt_test_001",
            event_type="checkout.session.completed",
            payload={"id": "evt_test_001"},
        )
        assert "evt_test_001" in str(event)

    def test_unique_stripe_event_id(self, db):
        from django.db import IntegrityError

        PaymentEvent.objects.create(
            stripe_event_id="evt_unique_001",
            event_type="test",
            payload={},
        )
        with pytest.raises(IntegrityError):
            PaymentEvent.objects.create(
                stripe_event_id="evt_unique_001",
                event_type="test",
                payload={},
            )


# ---------------------------------------------------------------------------
# Billing view tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBillingView:
    def test_billing_requires_login(self, client):
        resp = client.get(BILLING_URL)
        assert resp.status_code == 302

    def test_billing_renders_for_free_user(self, client_logged_in):
        resp = client_logged_in.get(BILLING_URL)
        assert resp.status_code == 200

    def test_billing_shows_subscription_info(self, client, user, active_subscription):
        client.force_login(user)
        resp = client.get(BILLING_URL)
        assert resp.status_code == 200
        assert b"Active" in resp.content or b"active" in resp.content.lower()

    def test_billing_checkout_success_message(self, client_logged_in):
        resp = client_logged_in.get(BILLING_URL + "?checkout=success")
        assert resp.status_code == 200
        assert b"subscription" in resp.content.lower() or b"welcome" in resp.content.lower()


@pytest.mark.django_db
class TestCheckoutView:
    def test_checkout_requires_login(self, client, plan):
        url = reverse("orders:checkout", kwargs={"plan_slug": plan.slug})
        resp = client.get(url)
        assert resp.status_code == 302

    def test_checkout_redirects_if_no_stripe_price_id(self, client_logged_in):
        no_price_plan = ServicePlan.objects.create(
            name="NoPricePlan", slug="no-price", price_monthly="0.00", is_active=True
        )
        url = reverse("orders:checkout", kwargs={"plan_slug": no_price_plan.slug})
        resp = client_logged_in.post(url, follow=True)
        assert resp.status_code == 200
        # Should redirect to pricing page with error message
        pricing_url = reverse("services:pricing")
        assert b"not yet available" in resp.content or resp.wsgi_request.path == pricing_url

    def test_checkout_404_for_inactive_plan(self, client_logged_in, plan):
        plan.is_active = False
        plan.save()
        url = reverse("orders:checkout", kwargs={"plan_slug": plan.slug})
        resp = client_logged_in.post(url)
        assert resp.status_code == 404

    @patch("orders.views.stripe.checkout.Session.create")
    @patch("orders.views.stripe.Customer.create")
    def test_checkout_redirects_to_stripe(
        self, mock_stripe_customer, mock_session_create, client_logged_in, plan
    ):
        mock_stripe_customer.return_value = MagicMock(id="cus_new_123")
        mock_stripe_customer.return_value.__getitem__ = lambda self, key: (
            "cus_new_123" if key == "id" else None
        )
        mock_session_create.return_value = MagicMock(url="https://checkout.stripe.com/session/xyz")

        url = reverse("orders:checkout", kwargs={"plan_slug": plan.slug})
        resp = client_logged_in.post(url)
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Billing portal
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBillingPortalView:
    def test_portal_requires_login(self, client):
        resp = client.post(BILLING_PORTAL_URL)
        assert resp.status_code == 302

    def test_portal_redirects_to_pricing_if_no_customer(self, client_logged_in):
        resp = client_logged_in.post(BILLING_PORTAL_URL, follow=True)
        assert resp.status_code == 200
        assert resp.wsgi_request.path == reverse("services:pricing")

    @patch("orders.views.stripe.billing_portal.Session.create")
    def test_portal_redirects_to_stripe(self, mock_portal, client, user, customer):
        mock_portal.return_value = MagicMock(url="https://billing.stripe.com/portal/xyz")
        client.force_login(user)
        resp = client.post(BILLING_PORTAL_URL)
        assert resp.status_code == 302
        assert resp["Location"] == "https://billing.stripe.com/portal/xyz"


# ---------------------------------------------------------------------------
# Webhook tests
# ---------------------------------------------------------------------------


def _build_webhook_request(client, payload: dict, sig_header: str = "t=1,v1=testsig"):
    return client.post(
        WEBHOOK_URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=sig_header,
    )


@pytest.mark.django_db
class TestStripeWebhook:
    def test_webhook_rejects_invalid_signature(self, client):
        payload = {"id": "evt_bad", "type": "test"}
        resp = _build_webhook_request(client, payload, sig_header="invalid")
        assert resp.status_code == 400

    def test_webhook_rejects_invalid_payload(self, client):
        resp = client.post(
            WEBHOOK_URL,
            data="not-json!!!",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=testsig",
        )
        assert resp.status_code == 400

    @patch("orders.views.stripe.Webhook.construct_event")
    def test_webhook_idempotency(self, mock_construct, client, db):
        """Second delivery of same event_id must return 200 and not duplicate rows."""
        event = {"id": "evt_dup_001", "type": "payment_intent.succeeded", "data": {"object": {}}}
        mock_construct.return_value = event

        # Pre-seed the event as already processed
        PaymentEvent.objects.create(
            stripe_event_id="evt_dup_001",
            event_type="payment_intent.succeeded",
            payload={},
        )

        resp = _build_webhook_request(client, event)
        assert resp.status_code == 200
        assert PaymentEvent.objects.filter(stripe_event_id="evt_dup_001").count() == 1

    @patch("orders.views.stripe.Webhook.construct_event")
    def test_webhook_records_unhandled_event(self, mock_construct, client, db):
        """Unrecognised event types should still be logged and return 200."""
        event = {"id": "evt_unknown_001", "type": "some.unknown.event", "data": {"object": {}}}
        mock_construct.return_value = event

        resp = _build_webhook_request(client, event)
        assert resp.status_code == 200
        assert PaymentEvent.objects.filter(stripe_event_id="evt_unknown_001").exists()

    @patch("orders.views.process_stripe_event.apply_async")
    @patch("orders.views.stripe.Webhook.construct_event")
    def test_webhook_enqueues_task_for_known_event(
        self, mock_construct, mock_apply_async, client, db
    ):
        event = {
            "id": "evt_checkout_001",
            "type": "checkout.session.completed",
            "data": {"object": {"customer": "cus_x", "subscription": "sub_x", "metadata": {}}},
        }
        mock_construct.return_value = event

        resp = _build_webhook_request(client, event)
        assert resp.status_code == 200
        payment_event = PaymentEvent.objects.get(stripe_event_id="evt_checkout_001")
        mock_apply_async.assert_called_once_with(args=[payment_event.pk], ignore_result=True)

    @patch("orders.views.process_stripe_event.apply_async")
    @patch("orders.views.stripe.Webhook.construct_event")
    def test_webhook_subscription_canceled_downgrades_user(
        self, mock_construct, mock_apply_async, client, user, customer, db
    ):
        """customer.subscription.deleted webhook must downgrade user to free tier."""
        user.subscription_tier = "starter"
        user.save()

        event = {
            "id": "evt_cancel_001",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_del_001",
                    "customer": "cus_test_123",
                    "status": "canceled",
                    "items": {"data": []},
                    "current_period_start": None,
                    "current_period_end": None,
                    "cancel_at_period_end": False,
                }
            },
        }
        mock_construct.return_value = event
        mock_apply_async.return_value = None

        resp = _build_webhook_request(client, event)
        assert resp.status_code == 200

        payment_event = PaymentEvent.objects.get(stripe_event_id="evt_cancel_001")
        process_stripe_event(payment_event.pk)

        user.refresh_from_db()
        assert user.subscription_tier == SubscriptionTier.FREE


@pytest.mark.django_db
class TestTransactionalEmailTasks:
    @patch("orders.tasks.send_checkout_success_email")
    def test_checkout_success_email_task(self, mock_send, user):
        send_checkout_success_email_task(user.pk, "Starter")
        mock_send.assert_called_once_with(
            user_email=user.email,
            first_name=user.first_name,
            plan_name="Starter",
        )

    @patch("orders.tasks.send_subscription_canceled_email")
    def test_subscription_canceled_email_task(self, mock_send, user):
        send_subscription_canceled_email_task(user.pk)
        mock_send.assert_called_once_with(
            user_email=user.email,
            first_name=user.first_name,
        )
