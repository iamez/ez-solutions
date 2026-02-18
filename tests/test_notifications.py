"""Tests for the notifications module — channels, dispatch, models, views."""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from notifications.channels import EmailChannel, SignalChannel, TelegramChannel
from notifications.dispatch import _get_recipient, notify_admin, notify_user
from notifications.models import NotificationLog, NotificationPreference

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    return User.objects.create_user(email="notify@test.com", password="testpass123!")


@pytest.fixture
def user_with_prefs(user):
    NotificationPreference.objects.create(
        user=user,
        email_enabled=True,
        telegram_enabled=True,
        signal_enabled=False,
        telegram_chat_id="123456789",
        signal_phone="",
    )
    return user


@pytest.fixture
def user_no_prefs(user):
    """User without any NotificationPreference object."""
    return user


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationPreference:
    def test_active_channels_all_enabled(self, db):
        u = User.objects.create_user(email="all@test.com", password="testpass123!")
        prefs = NotificationPreference.objects.create(
            user=u,
            email_enabled=True,
            telegram_enabled=True,
            signal_enabled=True,
            telegram_chat_id="999",
            signal_phone="+11234567890",
        )
        assert prefs.active_channels() == ["email", "telegram", "signal"]

    def test_active_channels_only_email(self, user):
        prefs = NotificationPreference.objects.create(user=user)
        assert prefs.active_channels() == ["email"]

    def test_active_channels_telegram_without_chat_id(self, user):
        prefs = NotificationPreference.objects.create(
            user=user, telegram_enabled=True, telegram_chat_id=""
        )
        # Telegram enabled but no chat_id → should not be in active list
        assert "telegram" not in prefs.active_channels()

    def test_str_representation(self, user):
        prefs = NotificationPreference.objects.create(user=user, email_enabled=True)
        assert "notify@test.com" in str(prefs)
        assert "email" in str(prefs)


@pytest.mark.django_db
class TestNotificationLog:
    def test_log_creation(self, user):
        log_entry = NotificationLog.objects.create(
            user=user,
            channel="email",
            subject="Test",
            recipient="notify@test.com",
            success=True,
        )
        assert log_entry.pk is not None
        assert log_entry.success is True

    def test_log_without_user(self):
        log_entry = NotificationLog.objects.create(
            user=None,
            channel="telegram",
            subject="Admin alert",
            recipient="123",
            success=False,
            error_message="Connection timeout",
        )
        assert log_entry.user is None
        assert log_entry.error_message == "Connection timeout"


# ---------------------------------------------------------------------------
# Channel tests
# ---------------------------------------------------------------------------


class TestEmailChannel:
    def test_is_configured(self):
        assert EmailChannel().is_configured() is True

    @patch("django.core.mail.send_mail")
    def test_send_plain_text(self, mock_send):
        mock_send.return_value = 1
        ch = EmailChannel()
        assert ch.send("test@test.com", "Subject", "Body") is True
        mock_send.assert_called_once()

    @patch("django.core.mail.EmailMultiAlternatives")
    def test_send_html(self, mock_email_cls):
        mock_msg = MagicMock()
        mock_msg.send.return_value = 1
        mock_email_cls.return_value = mock_msg
        ch = EmailChannel()
        assert ch.send("test@test.com", "Subject", "Body", html_body="<p>Hi</p>") is True
        mock_msg.attach_alternative.assert_called_once_with("<p>Hi</p>", "text/html")


class TestTelegramChannel:
    def test_is_configured_false_by_default(self, settings):
        settings.TELEGRAM_BOT_TOKEN = ""
        assert TelegramChannel().is_configured() is False

    def test_is_configured_true(self, settings):
        settings.TELEGRAM_BOT_TOKEN = "123:ABC"
        assert TelegramChannel().is_configured() is True

    @patch("httpx.post")
    def test_send_success(self, mock_post, settings):
        settings.TELEGRAM_BOT_TOKEN = "123:ABC"
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()
        ch = TelegramChannel()
        assert ch.send("999", "Hello", "World") is True
        call_args = mock_post.call_args
        assert "api.telegram.org" in call_args[0][0]
        # Check parse_mode is HTML (after the security fix)
        assert call_args[1]["json"]["parse_mode"] == "HTML"

    @patch("httpx.post")
    def test_send_failure(self, mock_post, settings):
        settings.TELEGRAM_BOT_TOKEN = "123:ABC"
        mock_post.side_effect = Exception("Network error")
        ch = TelegramChannel()
        assert ch.send("999", "Hello", "World") is False

    def test_send_no_token(self, settings):
        settings.TELEGRAM_BOT_TOKEN = ""
        ch = TelegramChannel()
        assert ch.send("999", "Hello", "World") is False


class TestSignalChannel:
    def test_is_configured_false(self, settings):
        settings.SIGNAL_CLI_REST_API_URL = ""
        settings.SIGNAL_SENDER_NUMBER = ""
        assert SignalChannel().is_configured() is False

    def test_is_configured_true(self, settings):
        settings.SIGNAL_CLI_REST_API_URL = "http://localhost:8080"
        settings.SIGNAL_SENDER_NUMBER = "+1234567890"
        assert SignalChannel().is_configured() is True

    @patch("httpx.post")
    def test_send_success(self, mock_post, settings):
        settings.SIGNAL_CLI_REST_API_URL = "http://localhost:8080"
        settings.SIGNAL_SENDER_NUMBER = "+1234567890"
        mock_post.return_value = MagicMock(status_code=201)
        mock_post.return_value.raise_for_status = MagicMock()
        ch = SignalChannel()
        assert ch.send("+0987654321", "Alert", "Body") is True


# ---------------------------------------------------------------------------
# Dispatch tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetRecipient:
    def test_email_channel(self, user):
        assert _get_recipient(user, "email") == "notify@test.com"

    def test_telegram_with_prefs(self, user_with_prefs):
        assert _get_recipient(user_with_prefs, "telegram") == "123456789"

    def test_telegram_without_prefs(self, user_no_prefs):
        assert _get_recipient(user_no_prefs, "telegram") == ""

    def test_signal_without_prefs(self, user_no_prefs):
        assert _get_recipient(user_no_prefs, "signal") == ""

    def test_unknown_channel(self, user):
        assert _get_recipient(user, "sms") == ""


@pytest.mark.django_db
class TestNotifyUser:
    @patch("notifications.dispatch.get_active_channels")
    def test_sends_to_email_by_default(self, mock_channels, user_no_prefs):
        mock_email = MagicMock()
        mock_email.send.return_value = True
        mock_channels.return_value = {"email": mock_email}

        results = notify_user(user_no_prefs, "Test", "Body")
        assert results == {"email": True}
        mock_email.send.assert_called_once()

    @patch("notifications.dispatch.get_active_channels")
    def test_respects_user_prefs(self, mock_channels, user_with_prefs):
        mock_email = MagicMock()
        mock_email.send.return_value = True
        mock_telegram = MagicMock()
        mock_telegram.send.return_value = True
        mock_channels.return_value = {"email": mock_email, "telegram": mock_telegram}

        results = notify_user(user_with_prefs, "Test", "Body")
        assert "email" in results
        assert "telegram" in results

    @patch("notifications.dispatch.get_active_channels")
    def test_explicit_channels_override(self, mock_channels, user_no_prefs):
        mock_email = MagicMock()
        mock_email.send.return_value = True
        mock_channels.return_value = {"email": mock_email}

        results = notify_user(user_no_prefs, "Test", "Body", channels=["email"])
        assert results == {"email": True}

    @patch("notifications.dispatch.get_active_channels")
    def test_logs_notification(self, mock_channels, user_no_prefs):
        mock_email = MagicMock()
        mock_email.send.return_value = True
        mock_channels.return_value = {"email": mock_email}

        notify_user(user_no_prefs, "Test Subject", "Body")
        # Should have created a NotificationLog entry
        assert NotificationLog.objects.filter(
            user=user_no_prefs, channel="email", subject="Test Subject", success=True
        ).exists()

    @patch("notifications.dispatch.get_active_channels")
    def test_handles_channel_exception(self, mock_channels, user_no_prefs):
        mock_email = MagicMock()
        mock_email.send.side_effect = Exception("SMTP error")
        mock_channels.return_value = {"email": mock_email}

        results = notify_user(user_no_prefs, "Test", "Body", channels=["email"])
        assert results == {"email": False}
        # Should have logged the failure
        assert NotificationLog.objects.filter(
            user=user_no_prefs, channel="email", success=False
        ).exists()


@pytest.mark.django_db
class TestNotifyAdmin:
    @patch("notifications.dispatch.get_active_channels")
    def test_sends_to_admin_email(self, mock_channels, settings):
        settings.DEFAULT_FROM_EMAIL = "admin@test.com"
        mock_email = MagicMock()
        mock_email.send.return_value = True
        mock_channels.return_value = {"email": mock_email}

        results = notify_admin("Alert", "Something happened")
        assert results == {"email": True}
        mock_email.send.assert_called_once()


# ---------------------------------------------------------------------------
# Signal tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTicketSignals:
    @patch("orders.tasks.send_ticket_notification_task.apply_async")
    def test_staff_reply_triggers_notification(self, mock_async):
        from tickets.models import Ticket, TicketMessage

        user = User.objects.create_user(email="customer@test.com", password="testpass123!")
        staff = User.objects.create_user(
            email="staff@test.com", password="testpass123!", is_staff=True
        )
        ticket = Ticket.objects.create(user=user, subject="Help me")
        TicketMessage.objects.create(
            ticket=ticket, sender=staff, body="We're on it!", is_staff_reply=True
        )
        mock_async.assert_called_once()
        args = mock_async.call_args
        assert args[1]["args"][2] == "customer@test.com"  # recipient is the customer

    @patch("orders.tasks.send_ticket_notification_task.apply_async")
    def test_customer_reply_notifies_staff(self, mock_async, settings):
        from tickets.models import Ticket, TicketMessage

        settings.DEFAULT_FROM_EMAIL = "support@ez-solutions.com"
        user = User.objects.create_user(email="customer2@test.com", password="testpass123!")
        ticket = Ticket.objects.create(user=user, subject="Question")
        TicketMessage.objects.create(
            ticket=ticket, sender=user, body="Any update?", is_staff_reply=False
        )
        mock_async.assert_called_once()
        args = mock_async.call_args
        assert args[1]["args"][2] == "support@ez-solutions.com"  # recipient is admin


@pytest.mark.django_db
class TestWelcomeSignal:
    @patch("orders.tasks.send_welcome_email_task.apply_async")
    def test_user_signup_enqueues_welcome_email(self, mock_async):
        """Test the signal handler directly."""
        from users.signals import on_user_signed_up

        user = User.objects.create_user(email="newuser@test.com", password="testpass123!")
        on_user_signed_up(sender=None, request=None, user=user)
        mock_async.assert_called_once()
        assert mock_async.call_args[1]["args"] == [user.pk]


# ---------------------------------------------------------------------------
# Unsubscribe token tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUnsubscribeViews:
    def test_preferences_requires_login(self, client):
        from django.urls import reverse

        resp = client.get(reverse("notifications:preferences"))
        assert resp.status_code == 302  # redirect to login

    def test_preferences_page_loads(self, client, user):
        from django.urls import reverse

        client.force_login(user)
        resp = client.get(reverse("notifications:preferences"))
        assert resp.status_code == 200
        assert b"Notification Preferences" in resp.content

    def test_preferences_save(self, client, user):
        from django.urls import reverse

        client.force_login(user)
        resp = client.post(
            reverse("notifications:preferences"),
            {
                "email_enabled": "on",
                "telegram_chat_id": "12345",
            },
        )
        assert resp.status_code == 302
        prefs = NotificationPreference.objects.get(user=user)
        assert prefs.email_enabled is True
        assert prefs.telegram_enabled is False
        assert prefs.telegram_chat_id == "12345"

    def test_unsubscribe_valid_token(self, client, user):
        from notifications.views import make_unsubscribe_token

        token = make_unsubscribe_token(user.pk)
        resp = client.get(f"/notifications/unsubscribe/{token}/")
        assert resp.status_code == 200
        assert b"unsubscribe" in resp.content.lower()

    def test_unsubscribe_post_disables_email(self, client, user):
        from notifications.views import make_unsubscribe_token

        NotificationPreference.objects.create(user=user, email_enabled=True)
        token = make_unsubscribe_token(user.pk)
        resp = client.post(f"/notifications/unsubscribe/{token}/")
        assert resp.status_code == 200
        prefs = NotificationPreference.objects.get(user=user)
        assert prefs.email_enabled is False

    def test_unsubscribe_invalid_token(self, client):
        resp = client.get("/notifications/unsubscribe/invalid-token/")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Seed plans command test
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSeedPlansCommand:
    def test_seed_creates_plans(self):
        from django.core.management import call_command

        from services.models import ServicePlan

        call_command("seed_plans")
        assert ServicePlan.objects.count() >= 3

    def test_seed_idempotent(self):
        from django.core.management import call_command

        from services.models import ServicePlan

        call_command("seed_plans")
        count1 = ServicePlan.objects.count()
        call_command("seed_plans")
        count2 = ServicePlan.objects.count()
        assert count1 == count2

    def test_seed_clear(self):
        from django.core.management import call_command

        from services.models import ServicePlan

        call_command("seed_plans")
        assert ServicePlan.objects.count() > 0
        call_command("seed_plans", "--clear")
        # After --clear, plans should be recreated
        assert ServicePlan.objects.count() >= 3
