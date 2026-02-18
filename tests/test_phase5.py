"""
Phase 5 tests — Provisioning, Webhooks (new paths), Staff Tickets,
                 Order History, Payment-failed email, Celery tasks.
"""

import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from orders.emailing import send_payment_failed_email
from orders.models import (
    Customer,
    Order,
    OrderStatus,
    ProvisioningJob,
    ProvisioningStatus,
    Subscription,
    SubscriptionStatus,
    VPSInstance,
    VPSInstanceStatus,
)
from orders.provisioning import PLAN_SPECS, DemoProvider, get_provider
from orders.tasks import provision_vps_task, send_payment_failed_email_task
from orders.webhooks import (
    _handle_checkout_completed,
    _handle_payment_failed,
    _handle_subscription_change,
    handle_event,
)
from services.models import ServicePlan
from tickets.models import Ticket, TicketMessage, TicketPriority, TicketStatus
from users.models import SubscriptionTier, User

STAFF_LIST_URL = reverse("tickets:staff_list")
ORDER_HISTORY_URL = reverse("orders:order_history")


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
def plan_no_tier(db):
    """A plan that has no tier_key — should NOT trigger provisioning."""
    return ServicePlan.objects.create(
        name="Free",
        slug="free",
        price_monthly="0.00",
        tier_key="",
        is_active=True,
    )


@pytest.fixture
def pro_plan(db):
    return ServicePlan.objects.create(
        name="Professional",
        slug="professional",
        price_monthly="79.00",
        tier_key="professional",
        stripe_price_id_monthly="price_test_pro",
        stripe_price_id_annual="price_test_pro_annual",
        is_active=True,
    )


@pytest.fixture
def customer(db, user):
    return Customer.objects.create(user=user, stripe_customer_id="cus_test_500")


@pytest.fixture
def active_subscription(db, customer):
    return Subscription.objects.create(
        customer=customer,
        stripe_subscription_id="sub_test_500",
        stripe_price_id="price_test_starter",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=timezone.now() + datetime.timedelta(days=30),
    )


@pytest.fixture
def order(db, customer, plan, active_subscription):
    return Order.objects.create(
        customer=customer,
        service_plan=plan,
        subscription=active_subscription,
        status=OrderStatus.PAID,
        stripe_checkout_session_id="cs_test_500",
        amount_total=Decimal("29.00"),
        currency="usd",
    )


@pytest.fixture
def provisioning_job(db, order):
    return ProvisioningJob.objects.create(
        order=order,
        provider="demo",
        status=ProvisioningStatus.QUEUED,
        payload={"plan_slug": "starter", "tier_key": "starter"},
    )


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        email="staff@ez-solutions.com",
        password="StaffPass123!",
        first_name="Staff",
        last_name="Member",
        is_staff=True,
    )


@pytest.fixture
def ticket(db, user):
    t = Ticket.objects.create(
        user=user,
        subject="Test ticket",
        status=TicketStatus.OPEN,
        priority=TicketPriority.NORMAL,
    )
    TicketMessage.objects.create(
        ticket=t, sender=user, body="Initial message", is_staff_reply=False
    )
    return t


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="other@example.com",
        password="OtherPass123!",
    )


@pytest.fixture
def other_ticket(db, other_user):
    return Ticket.objects.create(
        user=other_user,
        subject="Other users ticket",
        status=TicketStatus.OPEN,
        priority=TicketPriority.HIGH,
    )


# ---------------------------------------------------------------------------
# 1. orders/provisioning.py — VPS Provider abstraction
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDemoProvider:
    def test_provision_returns_valid_keys(self, provisioning_job):
        provider = DemoProvider()
        result = provider.provision(provisioning_job)
        assert "external_id" in result
        assert "ip_address" in result
        assert "vmid" in result

    def test_provision_external_id_is_uuid(self, provisioning_job):
        import uuid

        provider = DemoProvider()
        result = provider.provision(provisioning_job)
        uuid.UUID(result["external_id"])  # raises ValueError if invalid

    def test_provision_ip_address_format(self, provisioning_job):
        provider = DemoProvider()
        result = provider.provision(provisioning_job)
        parts = result["ip_address"].split(".")
        assert len(parts) == 4
        assert parts[0] == "10" and parts[1] == "0"

    def test_provision_vmid_is_int(self, provisioning_job):
        provider = DemoProvider()
        result = provider.provision(provisioning_job)
        assert isinstance(result["vmid"], int)
        assert 100 <= result["vmid"] <= 999

    def test_start_returns_true(self):
        provider = DemoProvider()
        mock_instance = MagicMock(hostname="test-vps")
        assert provider.start(mock_instance) is True

    def test_stop_returns_true(self):
        provider = DemoProvider()
        mock_instance = MagicMock(hostname="test-vps")
        assert provider.stop(mock_instance) is True

    def test_restart_returns_true(self):
        provider = DemoProvider()
        mock_instance = MagicMock(hostname="test-vps")
        assert provider.restart(mock_instance) is True

    def test_terminate_returns_true(self):
        provider = DemoProvider()
        mock_instance = MagicMock(hostname="test-vps")
        assert provider.terminate(mock_instance) is True

    def test_status_returns_running(self):
        provider = DemoProvider()
        mock_instance = MagicMock(hostname="test-vps")
        assert provider.status(mock_instance) == "running"


class TestGetProvider:
    def test_get_provider_demo(self):
        provider = get_provider("demo")
        assert isinstance(provider, DemoProvider)

    def test_get_provider_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown VPS provider"):
            get_provider("unknown")

    def test_get_provider_default_is_demo(self):
        provider = get_provider()
        assert isinstance(provider, DemoProvider)


class TestPlanSpecs:
    def test_has_starter_key(self):
        assert "starter" in PLAN_SPECS

    def test_has_professional_key(self):
        assert "professional" in PLAN_SPECS

    def test_has_enterprise_key(self):
        assert "enterprise" in PLAN_SPECS

    def test_starter_specs_structure(self):
        spec = PLAN_SPECS["starter"]
        assert spec["cpu_cores"] == 1
        assert spec["ram_mb"] == 1024
        assert spec["disk_gb"] == 20
        assert "os_template" in spec

    def test_enterprise_higher_than_starter(self):
        assert PLAN_SPECS["enterprise"]["cpu_cores"] > PLAN_SPECS["starter"]["cpu_cores"]
        assert PLAN_SPECS["enterprise"]["ram_mb"] > PLAN_SPECS["starter"]["ram_mb"]
        assert PLAN_SPECS["enterprise"]["disk_gb"] > PLAN_SPECS["starter"]["disk_gb"]


# ---------------------------------------------------------------------------
# 2. orders/webhooks.py — Checkout, Subscription change, Payment failed
# ---------------------------------------------------------------------------


def _make_stripe_sub_dict(sub_id="sub_new_001", status="active", price_id="price_test_starter"):
    """Helper to build a fake Stripe subscription dict."""
    return {
        "id": sub_id,
        "status": status,
        "items": {"data": [{"price": {"id": price_id}}]},
        "current_period_start": int(timezone.now().timestamp()),
        "current_period_end": int((timezone.now() + datetime.timedelta(days=30)).timestamp()),
        "cancel_at_period_end": False,
    }


@pytest.mark.django_db
class TestHandleCheckoutCompleted:
    @patch("orders.webhooks.stripe.Subscription.retrieve")
    @patch("orders.webhooks._queue_checkout_success_email")
    @patch("orders.webhooks._queue_provisioning")
    def test_creates_order_with_correct_fields(
        self, mock_prov, mock_email, mock_stripe_retrieve, customer, plan
    ):
        mock_stripe_retrieve.return_value = _make_stripe_sub_dict()
        session = {
            "id": "cs_test_new_001",
            "customer": customer.stripe_customer_id,
            "subscription": "sub_new_001",
            "amount_total": 2900,
            "currency": "usd",
            "payment_intent": "pi_test_001",
            "metadata": {"plan_slug": plan.slug},
        }
        _handle_checkout_completed(session)

        order = Order.objects.get(stripe_checkout_session_id="cs_test_new_001")
        assert order.customer == customer
        assert order.service_plan == plan
        assert order.status == OrderStatus.PAID
        assert order.amount_total == Decimal("29.00")
        assert order.currency == "usd"
        assert order.stripe_payment_intent_id == "pi_test_001"

    @patch("orders.webhooks.stripe.Subscription.retrieve")
    @patch("orders.webhooks._queue_checkout_success_email")
    @patch("orders.webhooks._queue_provisioning")
    def test_queues_provisioning_for_paid_plan_with_tier(
        self, mock_prov, mock_email, mock_stripe_retrieve, customer, plan
    ):
        mock_stripe_retrieve.return_value = _make_stripe_sub_dict()
        session = {
            "id": "cs_test_prov_001",
            "customer": customer.stripe_customer_id,
            "subscription": "sub_new_prov",
            "amount_total": 2900,
            "currency": "usd",
            "payment_intent": "pi_test_prov",
            "metadata": {"plan_slug": plan.slug},
        }
        _handle_checkout_completed(session)
        mock_prov.assert_called_once()

    @patch("orders.webhooks.stripe.Subscription.retrieve")
    @patch("orders.webhooks._queue_checkout_success_email")
    @patch("orders.webhooks._queue_provisioning")
    def test_no_provisioning_for_plan_without_tier_key(
        self, mock_prov, mock_email, mock_stripe_retrieve, customer, plan_no_tier
    ):
        mock_stripe_retrieve.return_value = _make_stripe_sub_dict(sub_id="sub_free_001")
        session = {
            "id": "cs_test_free_001",
            "customer": customer.stripe_customer_id,
            "subscription": "sub_free_001",
            "amount_total": 0,
            "currency": "usd",
            "payment_intent": "pi_free_001",
            "metadata": {"plan_slug": plan_no_tier.slug},
        }
        _handle_checkout_completed(session)
        mock_prov.assert_not_called()

    @patch("orders.webhooks.stripe.Subscription.retrieve")
    @patch("orders.webhooks._queue_checkout_success_email")
    @patch("orders.webhooks._queue_provisioning")
    def test_skips_unknown_customer(self, mock_prov, mock_email, mock_stripe_retrieve, db):
        session = {
            "customer": "cus_nonexistent",
            "subscription": "sub_x",
            "metadata": {},
        }
        _handle_checkout_completed(session)
        assert Order.objects.count() == 0
        mock_prov.assert_not_called()

    @patch("orders.webhooks.stripe.Subscription.retrieve")
    @patch("orders.webhooks._queue_checkout_success_email")
    @patch("orders.webhooks._queue_provisioning")
    def test_skips_when_no_customer_or_subscription(
        self, mock_prov, mock_email, mock_stripe_retrieve, db
    ):
        _handle_checkout_completed({})
        mock_stripe_retrieve.assert_not_called()
        assert Order.objects.count() == 0

    @patch("orders.webhooks.stripe.Subscription.retrieve")
    @patch("orders.webhooks._queue_checkout_success_email")
    @patch("orders.webhooks._queue_provisioning")
    def test_updates_user_tier_on_checkout(
        self, mock_prov, mock_email, mock_stripe_retrieve, customer, plan
    ):
        mock_stripe_retrieve.return_value = _make_stripe_sub_dict()
        session = {
            "id": "cs_test_tier_001",
            "customer": customer.stripe_customer_id,
            "subscription": "sub_tier_001",
            "amount_total": 2900,
            "currency": "usd",
            "payment_intent": "pi_tier_001",
            "metadata": {"plan_slug": plan.slug},
        }
        _handle_checkout_completed(session)
        customer.user.refresh_from_db()
        assert customer.user.subscription_tier == SubscriptionTier.STARTER


@pytest.mark.django_db
class TestHandleSubscriptionChange:
    @patch("orders.webhooks._queue_subscription_canceled_email")
    def test_sync_tier_on_upgrade_active(
        self, mock_cancel_email, customer, plan, pro_plan, active_subscription
    ):
        """Active subscription with a new price → user tier synced."""
        sub_dict = _make_stripe_sub_dict(
            sub_id=active_subscription.stripe_subscription_id,
            status="active",
            price_id="price_test_pro",
        )
        sub_dict["customer"] = customer.stripe_customer_id

        _handle_subscription_change(sub_dict)
        customer.user.refresh_from_db()
        assert customer.user.subscription_tier == SubscriptionTier.PROFESSIONAL

    @patch("orders.webhooks._queue_subscription_canceled_email")
    def test_downgrade_to_free_on_cancel(
        self, mock_cancel_email, customer, plan, active_subscription
    ):
        # Set user to starter first
        customer.user.subscription_tier = SubscriptionTier.STARTER
        customer.user.save(update_fields=["subscription_tier"])

        sub_dict = _make_stripe_sub_dict(
            sub_id=active_subscription.stripe_subscription_id,
            status="canceled",
            price_id="price_test_starter",
        )
        sub_dict["customer"] = customer.stripe_customer_id

        _handle_subscription_change(sub_dict)
        customer.user.refresh_from_db()
        assert customer.user.subscription_tier == SubscriptionTier.FREE

    @patch("orders.webhooks._queue_subscription_canceled_email")
    def test_unknown_customer_does_nothing(self, mock_cancel_email, db):
        sub_dict = _make_stripe_sub_dict()
        sub_dict["customer"] = "cus_nonexistent"
        _handle_subscription_change(sub_dict)
        mock_cancel_email.assert_not_called()


@pytest.mark.django_db
class TestHandlePaymentFailed:
    @patch("orders.webhooks._queue_payment_failed_email")
    def test_queues_email_for_known_customer(self, mock_queue, customer):
        invoice = {
            "customer": customer.stripe_customer_id,
            "amount_due": 2900,
            "currency": "usd",
        }
        _handle_payment_failed(invoice)
        mock_queue.assert_called_once_with(customer.user.pk, "29", "usd")

    @patch("orders.webhooks._queue_payment_failed_email")
    def test_skips_unknown_customer(self, mock_queue, db):
        invoice = {
            "customer": "cus_ghost",
            "amount_due": 500,
            "currency": "eur",
        }
        _handle_payment_failed(invoice)
        mock_queue.assert_not_called()

    @patch("orders.webhooks._queue_payment_failed_email")
    def test_skips_missing_customer_id(self, mock_queue, db):
        _handle_payment_failed({})
        mock_queue.assert_not_called()


@pytest.mark.django_db
class TestHandleEventDispatch:
    @patch("orders.webhooks._handle_checkout_completed")
    def test_routes_checkout_completed(self, mock_handler):
        handle_event(
            {
                "type": "checkout.session.completed",
                "data": {"object": {"id": "cs_xyz"}},
            }
        )
        mock_handler.assert_called_once_with({"id": "cs_xyz"})

    @patch("orders.webhooks._handle_subscription_change")
    def test_routes_subscription_updated(self, mock_handler):
        handle_event(
            {
                "type": "customer.subscription.updated",
                "data": {"object": {"id": "sub_xyz"}},
            }
        )
        mock_handler.assert_called_once()

    @patch("orders.webhooks._handle_payment_failed")
    def test_routes_payment_failed(self, mock_handler):
        handle_event(
            {
                "type": "invoice.payment_failed",
                "data": {"object": {"id": "in_xyz"}},
            }
        )
        mock_handler.assert_called_once()


# ---------------------------------------------------------------------------
# 3. orders/tasks.py — provision_vps_task, send_payment_failed_email_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProvisionVpsTask:
    @patch("orders.tasks._queue_vps_ready_notification")
    def test_creates_vps_instance_on_success(self, mock_notify, provisioning_job):
        provision_vps_task.run(provisioning_job.pk)

        assert VPSInstance.objects.filter(provisioning_job=provisioning_job).exists()
        instance = VPSInstance.objects.get(provisioning_job=provisioning_job)
        assert instance.status == VPSInstanceStatus.RUNNING
        assert instance.ip_address  # non-empty
        assert instance.hostname  # non-empty
        assert instance.cpu_cores == PLAN_SPECS["starter"]["cpu_cores"]
        assert instance.ram_mb == PLAN_SPECS["starter"]["ram_mb"]

    @patch("orders.tasks._queue_vps_ready_notification")
    def test_marks_job_as_ready(self, mock_notify, provisioning_job):
        provision_vps_task.run(provisioning_job.pk)
        provisioning_job.refresh_from_db()
        assert provisioning_job.status == ProvisioningStatus.READY
        assert provisioning_job.external_id != ""
        assert provisioning_job.completed_at is not None

    def test_handles_missing_provisioning_job(self, db):
        """No exception should be raised for a missing job — just return."""
        provision_vps_task.run(999999)  # non-existent PK

    @patch("orders.tasks._queue_vps_ready_notification")
    def test_skips_already_completed_job(self, mock_notify, provisioning_job):
        provisioning_job.status = ProvisioningStatus.READY
        provisioning_job.save(update_fields=["status"])

        provision_vps_task.run(provisioning_job.pk)
        assert VPSInstance.objects.count() == 0  # nothing new created
        mock_notify.assert_not_called()

    @patch("orders.tasks._queue_vps_ready_notification")
    def test_hostname_contains_order_pk_and_slug(self, mock_notify, provisioning_job):
        provision_vps_task.run(provisioning_job.pk)
        instance = VPSInstance.objects.get(provisioning_job=provisioning_job)
        assert str(provisioning_job.order.pk) in instance.hostname
        assert provisioning_job.order.service_plan.slug in instance.hostname

    @patch("orders.tasks._queue_vps_ready_notification")
    @patch("orders.tasks._queue_vps_failed_notification")
    @patch("orders.provisioning.get_provider")
    def test_marks_job_failed_on_provider_error(
        self, mock_get_provider, mock_fail_notify, mock_ready_notify, provisioning_job
    ):
        mock_provider = MagicMock()
        mock_provider.provision.side_effect = RuntimeError("Cloud API down")
        mock_get_provider.return_value = mock_provider

        with pytest.raises(RuntimeError):
            provision_vps_task.run(provisioning_job.pk)

        provisioning_job.refresh_from_db()
        assert provisioning_job.status == ProvisioningStatus.FAILED
        assert "Cloud API down" in provisioning_job.error_message
        mock_fail_notify.assert_called_once()


@pytest.mark.django_db
class TestSendPaymentFailedEmailTask:
    @patch("orders.emailing.send_payment_failed_email")
    def test_sends_email(self, mock_send, user):
        send_payment_failed_email_task.run(user.pk, "29.00", "usd")
        mock_send.assert_called_once_with(
            user_email=user.email,
            first_name=user.first_name,
            amount="29.00",
            currency="usd",
        )

    @patch("orders.emailing.send_payment_failed_email")
    def test_handles_missing_user(self, mock_send, db):
        send_payment_failed_email_task.run(999999, "10.00", "eur")
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# 4. tickets/views.py — Staff ticket views
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStaffTicketList:
    def test_requires_login(self, client):
        resp = client.get(STAFF_LIST_URL)
        assert resp.status_code == 302

    def test_non_staff_redirected(self, client, user):
        client.force_login(user)
        resp = client.get(STAFF_LIST_URL)
        # staff_member_required redirects non-staff to admin login
        assert resp.status_code == 302
        assert "admin" in resp.url or "login" in resp.url

    def test_staff_can_access(self, client, staff_user, ticket):
        client.force_login(staff_user)
        resp = client.get(STAFF_LIST_URL)
        assert resp.status_code == 200

    def test_shows_all_tickets(self, client, staff_user, ticket, other_ticket):
        client.force_login(staff_user)
        resp = client.get(STAFF_LIST_URL)
        content = resp.content.decode()
        assert "Test ticket" in content
        assert "Other users ticket" in content

    def test_status_filter(self, client, staff_user, ticket, other_ticket):
        other_ticket.status = TicketStatus.RESOLVED
        other_ticket.save(update_fields=["status"])

        client.force_login(staff_user)
        resp = client.get(STAFF_LIST_URL + "?status=open")
        content = resp.content.decode()
        assert "Test ticket" in content
        assert "Other users ticket" not in content

    def test_priority_filter(self, client, staff_user, ticket, other_ticket):
        client.force_login(staff_user)
        resp = client.get(STAFF_LIST_URL + "?priority=high")
        content = resp.content.decode()
        # other_ticket has priority HIGH, ticket has NORMAL
        assert "Other users ticket" in content
        assert "Test ticket" not in content

    def test_search_by_subject(self, client, staff_user, ticket, other_ticket):
        client.force_login(staff_user)
        resp = client.get(STAFF_LIST_URL + "?q=Other")
        content = resp.content.decode()
        assert "Other users ticket" in content
        assert "Test ticket" not in content

    def test_search_by_user_email(self, client, staff_user, ticket, other_ticket, other_user):
        client.force_login(staff_user)
        resp = client.get(STAFF_LIST_URL + f"?q={other_user.email}")
        content = resp.content.decode()
        assert "Other users ticket" in content


@pytest.mark.django_db
class TestStaffTicketDetail:
    def _url(self, ticket):
        return reverse("tickets:staff_detail", kwargs={"pk": ticket.pk})

    def test_requires_login(self, client, ticket):
        resp = client.get(self._url(ticket))
        assert resp.status_code == 302

    def test_non_staff_redirected(self, client, user, ticket):
        client.force_login(user)
        resp = client.get(self._url(ticket))
        assert resp.status_code == 302

    def test_staff_can_view(self, client, staff_user, ticket):
        client.force_login(staff_user)
        resp = client.get(self._url(ticket))
        assert resp.status_code == 200
        assert b"Test ticket" in resp.content

    def test_staff_reply_creates_message_with_is_staff_reply(self, client, staff_user, ticket):
        client.force_login(staff_user)
        resp = client.post(
            self._url(ticket),
            {"body": "Staff response here", "action": "reply"},
            follow=True,
        )
        assert resp.status_code == 200
        msg = TicketMessage.objects.filter(ticket=ticket, body="Staff response here").first()
        assert msg is not None
        assert msg.is_staff_reply is True
        assert msg.sender == staff_user

    def test_staff_reply_sets_status_to_waiting(self, client, staff_user, ticket):
        client.force_login(staff_user)
        client.post(self._url(ticket), {"body": "We're looking into it.", "action": "reply"})
        ticket.refresh_from_db()
        assert ticket.status == TicketStatus.WAITING

    def test_staff_can_change_status(self, client, staff_user, ticket):
        client.force_login(staff_user)
        resp = client.post(
            self._url(ticket),
            {"action": "status", "status": TicketStatus.RESOLVED},
            follow=True,
        )
        assert resp.status_code == 200
        ticket.refresh_from_db()
        assert ticket.status == TicketStatus.RESOLVED

    def test_staff_can_view_any_users_ticket(self, client, staff_user, other_ticket):
        client.force_login(staff_user)
        resp = client.get(self._url(other_ticket))
        assert resp.status_code == 200
        assert b"Other users ticket" in resp.content

    def test_invalid_status_change_ignored(self, client, staff_user, ticket):
        original_status = ticket.status
        client.force_login(staff_user)
        client.post(self._url(ticket), {"action": "status", "status": "nonexistent"})
        ticket.refresh_from_db()
        assert ticket.status == original_status


# ---------------------------------------------------------------------------
# 5. orders/views.py — Order history
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOrderHistoryView:
    def test_requires_login(self, client):
        resp = client.get(ORDER_HISTORY_URL)
        assert resp.status_code == 302

    def test_shows_users_orders(self, client, user, order):
        client.force_login(user)
        resp = client.get(ORDER_HISTORY_URL)
        assert resp.status_code == 200

    def test_empty_state_for_new_user(self, client, user):
        """User without a Customer record gets empty page."""
        client.force_login(user)
        resp = client.get(ORDER_HISTORY_URL)
        assert resp.status_code == 200

    def test_does_not_show_other_users_orders(self, client, other_user, order):
        """other_user should see no orders even though one exists."""
        client.force_login(other_user)
        resp = client.get(ORDER_HISTORY_URL)
        assert resp.status_code == 200
        # Should not contain the order amount from another user
        assert b"cs_test_500" not in resp.content


# ---------------------------------------------------------------------------
# 6. orders/emailing.py — send_payment_failed_email
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSendPaymentFailedEmail:
    @patch("orders.emailing.render_to_string", return_value="rendered template")
    def test_sends_email_with_correct_subject(self, mock_render):
        result = send_payment_failed_email(
            user_email="buyer@example.com",
            first_name="Jane",
            amount="49.00",
            currency="usd",
        )
        assert result == 1  # 1 email sent
        assert len(mail.outbox) == 1
        msg = mail.outbox[0]
        assert msg.subject == "Action required: payment failed"
        assert "buyer@example.com" in msg.to

    @patch("orders.emailing.render_to_string", return_value="rendered template")
    def test_email_uses_html_alternative(self, mock_render):
        send_payment_failed_email(
            user_email="buyer@example.com",
            first_name="Jane",
            amount="49.00",
            currency="usd",
        )
        msg = mail.outbox[0]
        assert len(msg.alternatives) == 1
        alt_content, alt_type = msg.alternatives[0]
        assert alt_type == "text/html"

    @patch("orders.emailing.render_to_string", return_value="rendered template")
    def test_render_context_includes_amount_and_currency(self, mock_render):
        send_payment_failed_email(
            user_email="buyer@example.com",
            first_name="Jane",
            amount="49.00",
            currency="eur",
        )
        # Check that render_to_string was called with a context containing amount/currency
        calls = mock_render.call_args_list
        # Both txt and html template renders
        assert len(calls) == 2
        ctx = calls[0][0][1]  # second arg to first call
        assert ctx["amount"] == "49.00"
        assert ctx["currency"] == "EUR"
        assert ctx["name"] == "Jane"

    @patch("orders.emailing.render_to_string", return_value="rendered template")
    def test_fallback_greeting_when_no_first_name(self, mock_render):
        send_payment_failed_email(
            user_email="buyer@example.com",
            first_name="",
            amount="10.00",
            currency="usd",
        )
        ctx = mock_render.call_args_list[0][0][1]
        assert ctx["name"] == "there"
