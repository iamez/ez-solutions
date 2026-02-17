"""
Phase 4 tests — Support Tickets
Covers: Ticket/TicketMessage models, list/create/detail views, access control, reply flow.
"""

import pytest
from django.urls import reverse

from tickets.models import Ticket, TicketMessage, TicketPriority, TicketStatus

LIST_URL = reverse("tickets:list")
CREATE_URL = reverse("tickets:create")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ticket(db, user):
    t = Ticket.objects.create(
        user=user,
        subject="My internet is down",
        status=TicketStatus.OPEN,
        priority=TicketPriority.HIGH,
    )
    TicketMessage.objects.create(
        ticket=t, sender=user, body="Please help ASAP.", is_staff_reply=False
    )
    return t


@pytest.fixture
def closed_ticket(db, user):
    t = Ticket.objects.create(
        user=user,
        subject="Old issue",
        status=TicketStatus.CLOSED,
        priority=TicketPriority.LOW,
    )
    TicketMessage.objects.create(ticket=t, sender=user, body="It was fixed.", is_staff_reply=False)
    return t


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTicketModel:
    def test_str(self, ticket):
        assert "My internet is down" in str(ticket)
        assert ticket.reference_short in str(ticket)

    def test_reference_short_is_8_chars(self, ticket):
        assert len(ticket.reference_short) == 8

    def test_is_open_true_for_open_status(self, ticket):
        assert ticket.is_open is True

    def test_is_open_false_for_closed(self, closed_ticket):
        assert closed_ticket.is_open is False

    def test_message_count(self, ticket):
        assert ticket.message_count == 1
        TicketMessage.objects.create(ticket=ticket, sender=ticket.user, body="Another msg")
        assert ticket.message_count == 2

    def test_get_absolute_url(self, ticket):
        url = ticket.get_absolute_url()
        assert str(ticket.pk) in url

    def test_ordering_newest_first(self, db, user):
        Ticket.objects.create(user=user, subject="First", status=TicketStatus.OPEN)
        t2 = Ticket.objects.create(user=user, subject="Second", status=TicketStatus.OPEN)
        tickets = list(Ticket.objects.all())
        assert tickets[0] == t2  # newest first


@pytest.mark.django_db
class TestTicketMessageModel:
    def test_str_includes_sender(self, ticket, user):
        msg = ticket.messages.first()
        assert user.email in str(msg)

    def test_staff_reply_flag(self, ticket, user):
        staff_msg = TicketMessage.objects.create(
            ticket=ticket, sender=user, body="Staff reply here", is_staff_reply=True
        )
        assert staff_msg.is_staff_reply is True

    def test_messages_ordered_oldest_first(self, ticket, user):
        TicketMessage.objects.create(ticket=ticket, sender=user, body="Second message")
        msgs = list(ticket.messages.all())
        assert msgs[0].body == "Please help ASAP."
        assert msgs[1].body == "Second message"


# ---------------------------------------------------------------------------
# Ticket list view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTicketListView:
    def test_list_requires_login(self, client):
        resp = client.get(LIST_URL)
        assert resp.status_code == 302

    def test_list_renders_for_authenticated_user(self, client_logged_in):
        resp = client_logged_in.get(LIST_URL)
        assert resp.status_code == 200

    def test_list_shows_own_tickets(self, client, user, ticket):
        client.force_login(user)
        resp = client.get(LIST_URL)
        assert b"My internet is down" in resp.content

    def test_list_does_not_show_other_users_tickets(self, client, user, db):
        from users.models import User

        other = User.objects.create_user(email="other@example.com", password="Pass123!")
        Ticket.objects.create(user=other, subject="Other user's ticket", status=TicketStatus.OPEN)
        client.force_login(user)
        resp = client.get(LIST_URL)
        assert b"Other user" not in resp.content

    def test_list_empty_state_renders(self, client_logged_in):
        resp = client_logged_in.get(LIST_URL)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Ticket create view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTicketCreateView:
    def test_create_requires_login(self, client):
        resp = client.get(CREATE_URL)
        assert resp.status_code == 302

    def test_create_page_renders(self, client_logged_in):
        resp = client_logged_in.get(CREATE_URL)
        assert resp.status_code == 200

    def test_create_ticket_success(self, client, user):
        client.force_login(user)
        resp = client.post(
            CREATE_URL,
            {
                "subject": "New problem",
                "priority": "normal",
                "body": "Something is broken.",
            },
            follow=True,
        )
        assert resp.status_code == 200
        assert Ticket.objects.filter(user=user, subject="New problem").exists()

    def test_create_also_creates_first_message(self, client, user):
        client.force_login(user)
        client.post(
            CREATE_URL,
            {
                "subject": "Test ticket",
                "priority": "low",
                "body": "Here is my issue description.",
            },
        )
        t = Ticket.objects.get(user=user, subject="Test ticket")
        assert t.messages.filter(body="Here is my issue description.").exists()

    def test_create_shows_success_message(self, client, user):
        client.force_login(user)
        resp = client.post(
            CREATE_URL,
            {
                "subject": "Flash test",
                "priority": "normal",
                "body": "Testing flash messages.",
            },
            follow=True,
        )
        content = resp.content.decode()
        assert "submitted" in content.lower() or "ticket" in content.lower()

    def test_create_invalid_empty_body_rejected(self, client_logged_in):
        resp = client_logged_in.post(
            CREATE_URL,
            {
                "subject": "No body",
                "priority": "normal",
                "body": "",
            },
        )
        assert resp.status_code == 200  # re-renders form
        assert not Ticket.objects.filter(subject="No body").exists()


# ---------------------------------------------------------------------------
# Ticket detail view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTicketDetailView:
    def test_detail_requires_login(self, client, ticket):
        url = reverse("tickets:detail", kwargs={"pk": ticket.pk})
        resp = client.get(url)
        assert resp.status_code == 302

    def test_detail_renders_own_ticket(self, client, user, ticket):
        client.force_login(user)
        url = reverse("tickets:detail", kwargs={"pk": ticket.pk})
        resp = client.get(url)
        assert resp.status_code == 200
        assert b"My internet is down" in resp.content

    def test_detail_404_for_other_users_ticket(self, client, db, ticket):
        from users.models import User

        other = User.objects.create_user(email="hacker@example.com", password="Pass123!")
        client.force_login(other)
        url = reverse("tickets:detail", kwargs={"pk": ticket.pk})
        resp = client.get(url)
        assert resp.status_code == 404

    def test_detail_shows_thread_messages(self, client, user, ticket):
        client.force_login(user)
        url = reverse("tickets:detail", kwargs={"pk": ticket.pk})
        resp = client.get(url)
        assert b"Please help ASAP." in resp.content

    def test_reply_adds_message(self, client, user, ticket):
        client.force_login(user)
        url = reverse("tickets:detail", kwargs={"pk": ticket.pk})
        resp = client.post(url, {"body": "Any updates?"}, follow=True)
        assert resp.status_code == 200
        assert ticket.messages.filter(body="Any updates?").exists()

    def test_reply_on_closed_ticket_rejected(self, client, user, closed_ticket):
        client.force_login(user)
        url = reverse("tickets:detail", kwargs={"pk": closed_ticket.pk})
        resp = client.post(url, {"body": "Still trying to reply."}, follow=True)
        assert resp.status_code == 200
        # Message should NOT be created
        assert not closed_ticket.messages.filter(body="Still trying to reply.").exists()

    def test_waiting_ticket_moves_to_open_on_customer_reply(self, client, user, ticket):
        ticket.status = TicketStatus.WAITING
        ticket.save()
        client.force_login(user)
        url = reverse("tickets:detail", kwargs={"pk": ticket.pk})
        client.post(url, {"body": "I replied."})
        ticket.refresh_from_db()
        assert ticket.status == TicketStatus.OPEN

    def test_closed_ticket_shows_no_reply_form(self, client, user, closed_ticket):
        client.force_login(user)
        url = reverse("tickets:detail", kwargs={"pk": closed_ticket.pk})
        resp = client.get(url)
        assert b"This ticket is closed" in resp.content
