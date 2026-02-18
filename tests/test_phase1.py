"""
Phase 1 tests — Accounts & Auth
Covers: registration, login/logout, dashboard access control, profile update.
"""

import pytest
from django.urls import reverse

from users.models import User

from .conftest import TEST_USER_PASSWORD

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIGNUP_URL = reverse("account_signup")
LOGIN_URL = reverse("account_login")
LOGOUT_URL = reverse("account_logout")
DASHBOARD_URL = reverse("users:dashboard")
PROFILE_URL = reverse("users:profile")


def _reg_payload(email="new@example.com", password="Str0ng!Pass99"):  # noqa: S107
    return {
        "email": email,
        "password1": password,
        "password2": password,
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRegistration:
    def test_signup_page_renders(self, client):
        resp = client.get(SIGNUP_URL)
        assert resp.status_code == 200
        assert b"form" in resp.content.lower()

    def test_registration_creates_user(self, client):
        payload = _reg_payload()
        client.post(SIGNUP_URL, payload)
        assert User.objects.filter(email="new@example.com").exists()

    def test_new_user_defaults_to_free_tier(self, client):
        client.post(SIGNUP_URL, _reg_payload())
        u = User.objects.get(email="new@example.com")
        assert u.subscription_tier == "free"
        assert u.is_paid is False

    def test_duplicate_email_rejected(self, client, user):
        payload = _reg_payload(email=user.email)
        client.post(SIGNUP_URL, payload)
        # allauth re-renders the form on error (200) or redirects if it somehow passes
        # Either way the user count stays at 1
        assert User.objects.filter(email=user.email).count() == 1


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLogin:
    def test_login_page_renders(self, client):
        resp = client.get(LOGIN_URL)
        assert resp.status_code == 200

    def test_valid_login_redirects_to_dashboard(self, client, user):
        resp = client.post(
            LOGIN_URL,
            {"login": user.email, "password": TEST_USER_PASSWORD},
            follow=True,
        )
        assert resp.status_code == 200
        # Landed on the dashboard (allauth may chain through /accounts/login/)
        assert resp.wsgi_request.path == DASHBOARD_URL, (
            f"Expected to land on {DASHBOARD_URL}, ended up at {resp.wsgi_request.path}. "
            f"Redirect chain: {resp.redirect_chain}"
        )

    def test_invalid_login_shows_error(self, client, user):
        resp = client.post(
            LOGIN_URL,
            {"login": user.email, "password": "WRONG"},
        )
        # Wrong credentials: allauth re-renders login (200) or redirects back (302).
        # Either way the user is NOT logged in and NOT on the dashboard.
        assert resp.status_code in (200, 302)
        if resp.status_code == 302:
            assert DASHBOARD_URL not in resp["Location"]
        else:
            # Form re-rendered — the login page is shown again
            assert b"Sign In" in resp.content or b"sign in" in resp.content.lower()

    def test_authenticated_user_redirected_from_login(self, client_logged_in):
        resp = client_logged_in.get(LOGIN_URL, follow=True)
        # allauth redirects already-authed users away from the login page
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLogout:
    def test_logout_page_renders(self, client_logged_in):
        resp = client_logged_in.get(LOGOUT_URL)
        assert resp.status_code == 200

    def test_logout_post_redirects(self, client_logged_in):
        resp = client_logged_in.post(LOGOUT_URL, follow=True)
        assert resp.status_code == 200
        # After logout, revisiting dashboard should redirect to login
        resp2 = client_logged_in.get(DASHBOARD_URL)
        assert resp2.status_code == 302


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDashboard:
    def test_dashboard_requires_login(self, client):
        resp = client.get(DASHBOARD_URL)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp["Location"] or "login" in resp["Location"]

    def test_dashboard_authenticated(self, client_logged_in):
        resp = client_logged_in.get(DASHBOARD_URL)
        assert resp.status_code == 200

    def test_dashboard_shows_user_name(self, client, user):
        user.first_name = "Alice"
        user.save()
        client.force_login(user)
        resp = client.get(DASHBOARD_URL)
        assert b"Alice" in resp.content

    def test_dashboard_shows_upgrade_banner_for_free_user(self, client_logged_in, user):
        assert user.subscription_tier == "free"
        resp = client_logged_in.get(DASHBOARD_URL)
        content = resp.content.decode()
        assert "upgrade" in content.lower() or "starter" in content.lower()


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProfile:
    def test_profile_requires_login(self, client):
        resp = client.get(PROFILE_URL)
        assert resp.status_code == 302

    def test_profile_page_renders(self, client_logged_in):
        resp = client_logged_in.get(PROFILE_URL)
        assert resp.status_code == 200

    def test_profile_update_saves_name(self, client, user):
        client.force_login(user)
        resp = client.post(
            PROFILE_URL,
            {"first_name": "Bob", "last_name": "Smith"},
            follow=True,
        )
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.first_name == "Bob"
        assert user.last_name == "Smith"

    def test_profile_update_shows_success_message(self, client, user):
        client.force_login(user)
        resp = client.post(
            PROFILE_URL,
            {"first_name": "Carol", "last_name": "Jones"},
            follow=True,
        )
        content = resp.content.decode()
        assert "updated" in content.lower() or "success" in content.lower()

    def test_profile_displays_email(self, client_logged_in, user):
        resp = client_logged_in.get(PROFILE_URL)
        assert user.email.encode() in resp.content
