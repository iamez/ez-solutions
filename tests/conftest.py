"""
Global pytest configuration and shared fixtures.
"""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    """A basic active user."""
    return User.objects.create_user(
        email="test@ez-solutions.com",
        password="StrongPass123!",
        first_name="Test",
        last_name="User",
    )


@pytest.fixture
def superuser(db):
    """A superuser for admin tests."""
    return User.objects.create_superuser(
        email="admin@ez-solutions.com",
        password="AdminPass123!",
    )


@pytest.fixture
def client_logged_in(client, user):
    """Django test client already logged-in as a regular user."""
    client.force_login(user)
    return client
