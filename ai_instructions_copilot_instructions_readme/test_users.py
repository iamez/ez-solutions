"""
Tech-IT Solutions - Users App Tests
Test suite for user authentication, registration, and profile management
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.users.models import Subscription

User = get_user_model()


class UserRegistrationTests(TestCase):
    """Test user registration functionality"""

    def setUp(self):
        self.client = Client()
        self.register_url = reverse("users:register")

    def test_registration_page_loads(self):
        """Test that registration page is accessible"""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Register")

    def test_successful_registration(self):
        """Test successful user registration"""
        data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password1": "TestPass123!",
            "password2": "TestPass123!",
            "first_name": "John",
            "last_name": "Doe",
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    def test_duplicate_email_registration(self):
        """Test that duplicate email registration fails"""
        User.objects.create_user(
            username="existing", email="existing@example.com", password="TestPass123!"
        )
        data = {
            "email": "existing@example.com",
            "username": "newuser",
            "password1": "TestPass123!",
            "password2": "TestPass123!",
        }
        response = self.client.post(self.register_url, data)
        self.assertFormError(
            response, "form", "email", "User with this Email already exists."
        )

    def test_password_mismatch(self):
        """Test that password mismatch is caught"""
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "password1": "TestPass123!",
            "password2": "DifferentPass123!",
        }
        response = self.client.post(self.register_url, data)
        self.assertFormError(
            response, "form", "password2", "The two password fields didn't match."
        )


class UserLoginTests(TestCase):
    """Test user login functionality"""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse("users:login")
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPass123!"
        )

    def test_login_page_loads(self):
        """Test that login page is accessible"""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Login")

    def test_successful_login(self):
        """Test successful login"""
        data = {"username": "test@example.com", "password": "TestPass123!"}
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_invalid_credentials(self):
        """Test login with invalid credentials"""
        data = {"username": "test@example.com", "password": "WrongPassword123!"}
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct")

    def test_inactive_user_cannot_login(self):
        """Test that inactive users cannot login"""
        self.user.is_active = False
        self.user.save()
        data = {"username": "test@example.com", "password": "TestPass123!"}
        response = self.client.post(self.login_url, data)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class UserDashboardTests(TestCase):
    """Test user dashboard functionality"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPass123!"
        )
        self.dashboard_url = reverse("users:dashboard")

    def test_dashboard_requires_login(self):
        """Test that dashboard requires authentication"""
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_authenticated_user_can_access_dashboard(self):
        """Test that authenticated users can access dashboard"""
        self.client.login(username="test@example.com", password="TestPass123!")
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")


class SubscriptionTests(TestCase):
    """Test subscription functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPass123!"
        )

    def test_default_subscription_tier(self):
        """Test that new users get free tier by default"""
        subscription = Subscription.objects.create(user=self.user)
        self.assertEqual(subscription.tier, "free")
        self.assertTrue(subscription.is_active)

    def test_subscription_upgrade(self):
        """Test subscription tier upgrade"""
        subscription = Subscription.objects.create(user=self.user, tier="free")
        subscription.tier = "premium"
        subscription.save()
        self.assertEqual(subscription.tier, "premium")

    def test_subscription_expiration(self):
        """Test subscription expiration"""
        from datetime import datetime, timedelta

        subscription = Subscription.objects.create(
            user=self.user,
            tier="premium",
            expires_at=datetime.now() - timedelta(days=1),
        )
        self.assertFalse(subscription.is_valid())


class UserModelTests(TestCase):
    """Test User model functionality"""

    def test_user_creation(self):
        """Test creating a user"""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPass123!"
        )
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("TestPass123!"))

    def test_user_string_representation(self):
        """Test user string representation"""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPass123!"
        )
        self.assertEqual(str(user), "test@example.com")

    def test_superuser_creation(self):
        """Test creating a superuser"""
        admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="AdminPass123!"
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
