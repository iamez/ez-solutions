"""
Tech-IT Solutions - Services App Tests
Test suite for service management and pricing
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.services.models import Service, ServicePlan
from decimal import Decimal

User = get_user_model()


class ServiceModelTests(TestCase):
    """Test Service model"""

    def setUp(self):
        self.service = Service.objects.create(
            name="Web Hosting",
            slug="web-hosting",
            description="Professional web hosting",
            service_type="hosting",
            is_active=True,
        )

    def test_service_creation(self):
        """Test creating a service"""
        self.assertEqual(self.service.name, "Web Hosting")
        self.assertEqual(self.service.slug, "web-hosting")
        self.assertTrue(self.service.is_active)

    def test_service_string_representation(self):
        """Test service string representation"""
        self.assertEqual(str(self.service), "Web Hosting")

    def test_service_absolute_url(self):
        """Test service absolute URL"""
        url = self.service.get_absolute_url()
        self.assertEqual(url, f"/services/web-hosting/")


class ServicePlanTests(TestCase):
    """Test ServicePlan model"""

    def setUp(self):
        self.service = Service.objects.create(
            name="Web Hosting", slug="web-hosting", service_type="hosting"
        )
        self.plan = ServicePlan.objects.create(
            service=self.service,
            name="Basic Plan",
            price=Decimal("9.99"),
            billing_period="monthly",
            disk_space=10,
            bandwidth=100,
        )

    def test_plan_creation(self):
        """Test creating a service plan"""
        self.assertEqual(self.plan.name, "Basic Plan")
        self.assertEqual(self.plan.price, Decimal("9.99"))
        self.assertEqual(self.plan.billing_period, "monthly")

    def test_plan_features_list(self):
        """Test plan features parsing"""
        self.plan.features = "10GB Storage\n100GB Bandwidth\nFree SSL"
        self.plan.save()
        features = self.plan.get_features_list()
        self.assertEqual(len(features), 3)
        self.assertIn("10GB Storage", features)

    def test_annual_price_calculation(self):
        """Test annual price calculation"""
        annual_price = self.plan.get_annual_price()
        self.assertEqual(annual_price, Decimal("9.99") * 12)


class ServiceViewTests(TestCase):
    """Test service views"""

    def setUp(self):
        self.client = Client()
        self.service = Service.objects.create(
            name="Web Hosting",
            slug="web-hosting",
            service_type="hosting",
            is_active=True,
        )
        self.plan = ServicePlan.objects.create(
            service=self.service,
            name="Basic Plan",
            price=Decimal("9.99"),
            billing_period="monthly",
        )

    def test_service_list_view(self):
        """Test services list page"""
        response = self.client.get(reverse("services:service_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Web Hosting")

    def test_service_detail_view(self):
        """Test service detail page"""
        response = self.client.get(
            reverse("services:service_detail", kwargs={"slug": "web-hosting"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Web Hosting")
        self.assertContains(response, "Basic Plan")

    def test_inactive_service_not_shown(self):
        """Test that inactive services are not displayed"""
        self.service.is_active = False
        self.service.save()
        response = self.client.get(reverse("services:service_list"))
        self.assertNotContains(response, "Web Hosting")


class PricingTests(TestCase):
    """Test pricing calculations"""

    def setUp(self):
        self.service = Service.objects.create(
            name="VPS", slug="vps", service_type="vps"
        )

    def test_monthly_pricing(self):
        """Test monthly pricing"""
        plan = ServicePlan.objects.create(
            service=self.service,
            name="VPS-1",
            price=Decimal("29.99"),
            billing_period="monthly",
        )
        self.assertEqual(plan.price, Decimal("29.99"))

    def test_annual_discount(self):
        """Test annual discount calculation"""
        monthly_plan = ServicePlan.objects.create(
            service=self.service,
            name="VPS-Monthly",
            price=Decimal("29.99"),
            billing_period="monthly",
        )
        annual_plan = ServicePlan.objects.create(
            service=self.service,
            name="VPS-Annual",
            price=Decimal("299.99"),
            billing_period="annual",
        )
        monthly_annual = monthly_plan.get_annual_price()
        actual_annual = annual_plan.price
        savings = monthly_annual - actual_annual
        self.assertGreater(savings, 0)
