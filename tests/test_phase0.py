"""Phase 0 — smoke tests: project boots, User model works, core pages respond."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse

User = get_user_model()


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------
class TestUserModel:
    def test_create_user_with_email(self, db):
        user = User.objects.create_user(email="hello@test.com", password="Pass123!")
        assert user.pk is not None
        assert user.email == "hello@test.com"
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_create_user_requires_email(self, db):
        with pytest.raises(ValueError):
            User.objects.create_user(email="", password="Pass123!")

    def test_create_superuser(self, db):
        su = User.objects.create_superuser(email="admin@test.com", password="Pass123!")
        assert su.is_staff is True
        assert su.is_superuser is True

    def test_full_name_property(self, db):
        user = User.objects.create_user(
            email="jane@test.com",
            password="Pass123!",
            first_name="Jane",
            last_name="Doe",
        )
        assert user.full_name == "Jane Doe"

    def test_full_name_falls_back_to_email(self, db):
        user = User.objects.create_user(email="anon@test.com", password="Pass123!")
        assert user.full_name == "anon@test.com"

    def test_is_paid_free_tier(self, user):
        assert user.is_paid is False

    def test_str_returns_email(self, user):
        assert str(user) == "test@ez-solutions.com"

    def test_duplicate_email_raises(self, db):
        User.objects.create_user(email="dup@test.com", password="Pass123!")
        with pytest.raises(IntegrityError):
            User.objects.create_user(email="dup@test.com", password="Other123!")

    def test_create_superuser_is_staff_false_raises(self, db):
        with pytest.raises(ValueError, match="is_staff"):
            User.objects.create_superuser(
                email="bad_su@test.com", password="Pass123!", is_staff=False
            )

    def test_create_superuser_is_superuser_false_raises(self, db):
        with pytest.raises(ValueError, match="is_superuser"):
            User.objects.create_superuser(
                email="bad_su2@test.com", password="Pass123!", is_superuser=False
            )


# ---------------------------------------------------------------------------
# URL smoke tests
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestPublicPages:
    def test_homepage_returns_200(self, client):
        url = reverse("home:index")
        response = client.get(url)
        assert response.status_code == 200

    def test_about_returns_200(self, client):
        url = reverse("home:about")
        response = client.get(url)
        assert response.status_code == 200

    def test_dashboard_redirects_anonymous(self, client):
        url = reverse("users:dashboard")
        response = client.get(url)
        assert response.status_code == 302
        assert "/accounts/" in response["Location"]

    def test_dashboard_returns_200_when_logged_in(self, client_logged_in):
        url = reverse("users:dashboard")
        response = client_logged_in.get(url)
        assert response.status_code == 200

    def test_login_page_returns_200(self, client):
        url = reverse("account_login")
        response = client.get(url)
        assert response.status_code == 200

    def test_signup_page_returns_200(self, client):
        url = reverse("account_signup")
        response = client.get(url)
        assert response.status_code == 200
