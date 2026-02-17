"""
REST API tests — Phase 5: /api/health/, /api/v1/plans/, /api/v1/tickets/, /api/v1/me/
"""

import pytest
from rest_framework.test import APIClient

from orders.models import Customer, Subscription, SubscriptionStatus
from services.models import ServicePlan
from tickets.models import Ticket, TicketMessage, TicketPriority, TicketStatus

HEALTH_URL = "/api/health/"
PLANS_URL = "/api/v1/plans/"
TICKETS_URL = "/api/v1/tickets/"
ME_URL = "/api/v1/me/"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def plan(db):
    return ServicePlan.objects.create(
        name="Starter",
        slug="starter-api",
        price_monthly="9.00",
        tier_key="starter",
        is_active=True,
        is_featured=False,
        sort_order=1,
    )


@pytest.fixture
def featured_plan(db):
    return ServicePlan.objects.create(
        name="Professional",
        slug="professional-api",
        price_monthly="29.00",
        price_annual="290.00",
        tier_key="professional",
        is_active=True,
        is_featured=True,
        sort_order=2,
    )


@pytest.fixture
def inactive_plan(db):
    return ServicePlan.objects.create(
        name="Legacy",
        slug="legacy",
        price_monthly="5.00",
        tier_key="free",
        is_active=False,
    )


@pytest.fixture
def ticket(db, user):
    t = Ticket.objects.create(
        user=user,
        subject="API test ticket",
        status=TicketStatus.OPEN,
        priority=TicketPriority.NORMAL,
    )
    TicketMessage.objects.create(
        ticket=t, sender=user, body="Hello from API.", is_staff_reply=False
    )
    return t


@pytest.fixture
def closed_ticket(db, user):
    t = Ticket.objects.create(
        user=user,
        subject="Closed ticket",
        status=TicketStatus.CLOSED,
        priority=TicketPriority.LOW,
    )
    TicketMessage.objects.create(ticket=t, sender=user, body="Done.", is_staff_reply=False)
    return t


@pytest.fixture
def customer(db, user):
    return Customer.objects.create(user=user, stripe_customer_id="cus_api_test")


@pytest.fixture
def active_subscription(db, customer):
    import datetime

    from django.utils import timezone

    return Subscription.objects.create(
        customer=customer,
        stripe_subscription_id="sub_api_test",
        stripe_price_id="price_api_test",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=timezone.now() + datetime.timedelta(days=30),
    )


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHealth:
    def test_returns_ok(self, api_client):
        resp = api_client.get(HEALTH_URL)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_no_auth_required(self, api_client):
        # No credentials — still succeeds
        resp = api_client.get(HEALTH_URL)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Plans endpoint (public)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPlanList:
    def test_lists_active_plans_only(self, api_client, plan, inactive_plan):
        resp = api_client.get(PLANS_URL)
        assert resp.status_code == 200
        slugs = [p["slug"] for p in resp.json()]
        assert plan.slug in slugs
        assert inactive_plan.slug not in slugs

    def test_annual_savings_computed(self, api_client, featured_plan):
        resp = api_client.get(PLANS_URL)
        assert resp.status_code == 200
        data = next(p for p in resp.json() if p["slug"] == featured_plan.slug)
        # 29 * 12 - 290 = 58 → savings
        assert data["annual_savings"] is not None
        assert float(data["annual_savings"]) == pytest.approx(58.0)

    def test_annual_savings_null_when_no_annual_price(self, api_client, plan):
        resp = api_client.get(PLANS_URL)
        assert resp.status_code == 200
        data = next(p for p in resp.json() if p["slug"] == plan.slug)
        assert data["annual_savings"] is None

    def test_no_auth_required(self, api_client):
        resp = api_client.get(PLANS_URL)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tickets — list & create
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTicketList:
    def test_requires_auth(self, api_client):
        resp = api_client.get(TICKETS_URL)
        assert resp.status_code == 403

    def test_returns_own_tickets(self, auth_client, ticket):
        resp = auth_client.get(TICKETS_URL)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["subject"] == "API test ticket"

    def test_does_not_return_other_users_tickets(self, db, auth_client, user):
        from django.contrib.auth import get_user_model

        other = get_user_model().objects.create_user(
            email="other@ez-solutions.com", password="Pass123!"
        )
        Ticket.objects.create(user=other, subject="Other ticket", status=TicketStatus.OPEN)
        resp = auth_client.get(TICKETS_URL)
        assert resp.status_code == 200
        assert len(resp.json()) == 0


@pytest.mark.django_db
class TestTicketCreate:
    def test_requires_auth(self, api_client):
        resp = api_client.post(TICKETS_URL, {"subject": "x", "body": "y"})
        assert resp.status_code == 403

    def test_creates_ticket_with_first_message(self, auth_client, user):
        payload = {"subject": "Need help", "body": "My connection is slow.", "priority": "high"}
        resp = auth_client.post(TICKETS_URL, payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject"] == "Need help"
        assert data["status"] == TicketStatus.OPEN
        assert data["message_count"] == 1
        assert len(data["messages"]) == 1
        assert data["messages"][0]["body"] == "My connection is slow."

    def test_invalid_payload_returns_400(self, auth_client):
        resp = auth_client.post(TICKETS_URL, {})
        assert resp.status_code == 400

    def test_default_priority_is_normal(self, auth_client):
        resp = auth_client.post(TICKETS_URL, {"subject": "Test", "body": "Body"})
        assert resp.status_code == 201
        assert Ticket.objects.last().priority == TicketPriority.NORMAL


# ---------------------------------------------------------------------------
# Ticket detail
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTicketDetail:
    def test_requires_auth(self, api_client, ticket):
        resp = api_client.get(f"{TICKETS_URL}{ticket.pk}/")
        assert resp.status_code == 403

    def test_returns_ticket(self, auth_client, ticket):
        resp = auth_client.get(f"{TICKETS_URL}{ticket.pk}/")
        assert resp.status_code == 200
        assert resp.json()["subject"] == "API test ticket"

    def test_other_users_ticket_returns_404(self, db, auth_client):
        from django.contrib.auth import get_user_model

        other = get_user_model().objects.create_user(
            email="other2@ez-solutions.com", password="Pass123!"
        )
        other_ticket = Ticket.objects.create(
            user=other, subject="Not yours", status=TicketStatus.OPEN
        )
        resp = auth_client.get(f"{TICKETS_URL}{other_ticket.pk}/")
        assert resp.status_code == 404

    def test_nonexistent_ticket_returns_404(self, auth_client):
        resp = auth_client.get(f"{TICKETS_URL}99999/")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Ticket reply
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTicketReply:
    def _reply_url(self, pk):
        return f"{TICKETS_URL}{pk}/reply/"

    def test_requires_auth(self, api_client, ticket):
        resp = api_client.post(self._reply_url(ticket.pk), {"body": "hi"})
        assert resp.status_code == 403

    def test_adds_reply_to_open_ticket(self, auth_client, ticket):
        resp = auth_client.post(self._reply_url(ticket.pk), {"body": "Follow-up message."})
        assert resp.status_code == 201
        assert resp.json()["body"] == "Follow-up message."
        assert ticket.messages.count() == 2

    def test_cannot_reply_to_closed_ticket(self, auth_client, closed_ticket):
        resp = auth_client.post(self._reply_url(closed_ticket.pk), {"body": "Reopening?"})
        assert resp.status_code == 400
        assert "closed" in resp.json()["detail"].lower()

    def test_other_users_ticket_returns_404(self, db, auth_client):
        from django.contrib.auth import get_user_model

        other = get_user_model().objects.create_user(
            email="other3@ez-solutions.com", password="Pass123!"
        )
        other_ticket = Ticket.objects.create(
            user=other, subject="Not yours", status=TicketStatus.OPEN
        )
        resp = auth_client.post(self._reply_url(other_ticket.pk), {"body": "hi"})
        assert resp.status_code == 404

    def test_missing_body_returns_400(self, auth_client, ticket):
        resp = auth_client.post(self._reply_url(ticket.pk), {})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Me endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMe:
    def test_requires_auth(self, api_client):
        resp = api_client.get(ME_URL)
        assert resp.status_code == 403

    def test_returns_user_profile(self, auth_client, user):
        resp = auth_client.get(ME_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == user.email
        assert data["first_name"] == user.first_name

    def test_subscription_null_when_no_stripe_customer(self, auth_client):
        resp = auth_client.get(ME_URL)
        assert resp.status_code == 200
        assert resp.json()["subscription"] is None

    def test_subscription_returned_when_active(self, auth_client, active_subscription):
        resp = auth_client.get(ME_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["subscription"] is not None
        assert data["subscription"]["status"] == SubscriptionStatus.ACTIVE

    def test_patch_updates_name(self, auth_client, user):
        resp = auth_client.patch(ME_URL, {"first_name": "Alice", "last_name": "Smith"})
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.first_name == "Alice"
        assert user.last_name == "Smith"

    def test_patch_ignores_disallowed_fields(self, auth_client, user):
        resp = auth_client.patch(ME_URL, {"email": "hacker@evil.com"})
        # No allowed fields → 400
        assert resp.status_code == 400

    def test_patch_only_allowed_fields(self, auth_client, user):
        original_email = user.email
        resp = auth_client.patch(ME_URL, {"first_name": "Bob", "email": "hacker@evil.com"})
        # first_name accepted, email silently ignored
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.first_name == "Bob"
        assert user.email == original_email


# ---------------------------------------------------------------------------
# Robots.txt
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRobotsTxt:
    def test_serves_robots_txt(self, api_client):
        resp = api_client.get("/robots.txt")
        assert resp.status_code == 200
        assert "text/plain" in resp["Content-Type"]
        assert "User-agent: *" in resp.content.decode()
        assert "Disallow: /admin/" in resp.content.decode()

    def test_cache_header_set(self, api_client):
        resp = api_client.get("/robots.txt")
        assert "max-age" in resp.get("Cache-Control", "")
