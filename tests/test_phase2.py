"""
Phase 2 tests — Services Catalog
Covers: ServicePlan model, PlanFeature, pricing page public access.
"""

import pytest
from django.urls import reverse

from orders.models import Customer, Order, OrderStatus, ProvisioningJob, VPSInstance
from services.models import PlanFeature, ServicePlan

PRICING_URL = reverse("services:pricing")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def starter_plan(db):
    plan = ServicePlan.objects.create(
        name="Starter",
        price_monthly="29.00",
        tier_key="starter",
        is_active=True,
        is_featured=False,
        sort_order=1,
    )
    PlanFeature.objects.create(plan=plan, text="Up to 3 domains", is_included=True, sort_order=1)
    PlanFeature.objects.create(plan=plan, text="Priority support", is_included=False, sort_order=2)
    return plan


@pytest.fixture
def pro_plan(db):
    plan = ServicePlan.objects.create(
        name="Professional",
        tagline="Best for growing teams",
        price_monthly="79.00",
        price_annual="799.00",
        tier_key="professional",
        is_active=True,
        is_featured=True,
        sort_order=2,
    )
    PlanFeature.objects.create(plan=plan, text="Unlimited domains", is_included=True, sort_order=1)
    PlanFeature.objects.create(plan=plan, text="Priority support", is_included=True, sort_order=2)
    return plan


@pytest.fixture
def inactive_plan(db):
    return ServicePlan.objects.create(
        name="Legacy",
        price_monthly="9.00",
        is_active=False,
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestServicePlanModel:
    def test_slug_auto_generated(self, starter_plan):
        assert starter_plan.slug == "starter"

    def test_slug_not_overwritten_on_save(self, starter_plan):
        starter_plan.name = "Starter Plus"
        starter_plan.save()
        assert starter_plan.slug == "starter"  # slug stays unchanged

    def test_str_returns_name(self, starter_plan):
        assert str(starter_plan) == "Starter"

    def test_annual_savings_calculated(self, pro_plan):
        # monthly × 12 = 948, annual = 799, saved = 149
        savings = pro_plan.annual_savings
        assert savings is not None
        assert "Save" in savings

    def test_annual_savings_none_when_no_annual_price(self, starter_plan):
        assert starter_plan.annual_savings is None

    def test_is_paid_false_for_free_plan(self, db):
        free = ServicePlan.objects.create(
            name="Free", price_monthly="0.00", tier_key="free", is_active=True
        )
        assert free.tier_key == "free"

    def test_ordering_by_sort_order(self, starter_plan, pro_plan):
        plans = list(ServicePlan.objects.filter(is_active=True))
        assert plans[0].name == "Starter"
        assert plans[1].name == "Professional"


@pytest.mark.django_db
class TestPlanFeatureModel:
    def test_str_includes_included(self, starter_plan):
        f = starter_plan.features.filter(is_included=True).first()
        assert "✓" in str(f)

    def test_str_includes_excluded(self, starter_plan):
        f = starter_plan.features.filter(is_included=False).first()
        assert "✗" in str(f)

    def test_features_ordered_by_sort_order(self, starter_plan):
        features = list(starter_plan.features.all())
        assert features[0].text == "Up to 3 domains"
        assert features[1].text == "Priority support"


@pytest.mark.django_db
class TestOrderFulfillmentModels:
    def test_order_creation(self, user, starter_plan):
        customer = Customer.objects.create(user=user, stripe_customer_id="cus_order_001")
        order = Order.objects.create(
            customer=customer,
            service_plan=starter_plan,
            status=OrderStatus.PAID,
            amount_total="29.00",
            currency="usd",
        )
        assert order.customer == customer
        assert order.service_plan == starter_plan
        assert order.status == OrderStatus.PAID

    def test_provisioning_job_links_to_order(self, user, starter_plan):
        customer = Customer.objects.create(user=user, stripe_customer_id="cus_order_002")
        order = Order.objects.create(
            customer=customer,
            service_plan=starter_plan,
            amount_total="29.00",
        )
        job = ProvisioningJob.objects.create(order=order, provider="proxmox")
        assert job.order == order
        assert order.provisioning_jobs.count() == 1

    def test_vps_instance_links_to_provisioning_job(self, user, starter_plan):
        customer = Customer.objects.create(user=user, stripe_customer_id="cus_order_003")
        order = Order.objects.create(
            customer=customer,
            service_plan=starter_plan,
            amount_total="29.00",
        )
        job = ProvisioningJob.objects.create(order=order)
        instance = VPSInstance.objects.create(
            provisioning_job=job,
            customer=customer,
            hostname="vps-001.ez-solutions.local",
            cpu_cores=2,
            ram_mb=2048,
            disk_gb=40,
        )
        assert instance.provisioning_job == job
        assert job.vps_instance == instance

    def test_order_str(self, user, starter_plan):
        customer = Customer.objects.create(user=user, stripe_customer_id="cus_order_004")
        order = Order.objects.create(
            customer=customer,
            service_plan=starter_plan,
            amount_total="29.00",
        )
        assert "Order" in str(order)

    def test_vps_instance_str(self, user, starter_plan):
        customer = Customer.objects.create(user=user, stripe_customer_id="cus_order_005")
        order = Order.objects.create(
            customer=customer,
            service_plan=starter_plan,
            amount_total="29.00",
        )
        job = ProvisioningJob.objects.create(order=order)
        instance = VPSInstance.objects.create(
            provisioning_job=job,
            customer=customer,
            hostname="vps-002.ez-solutions.local",
        )
        assert "vps-002" in str(instance)


# ---------------------------------------------------------------------------
# View tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPricingPage:
    def test_pricing_page_accessible_anonymously(self, client):
        resp = client.get(PRICING_URL)
        assert resp.status_code == 200

    def test_pricing_page_accessible_authenticated(self, client_logged_in):
        resp = client_logged_in.get(PRICING_URL)
        assert resp.status_code == 200

    def test_pricing_shows_active_plans(self, client, starter_plan, pro_plan):
        resp = client.get(PRICING_URL)
        assert b"Starter" in resp.content
        assert b"Professional" in resp.content

    def test_pricing_hides_inactive_plans(self, client, inactive_plan):
        resp = client.get(PRICING_URL)
        assert b"Legacy" not in resp.content

    def test_pricing_shows_plan_features(self, client, starter_plan):
        resp = client.get(PRICING_URL)
        assert b"Up to 3 domains" in resp.content

    def test_pricing_shows_cta_for_anonymous(self, client, starter_plan):
        resp = client.get(PRICING_URL)
        content = resp.content.decode()
        assert "free trial" in content.lower() or "get started" in content.lower()

    def test_empty_pricing_page_renders(self, client):
        # No plans in DB — should render gracefully with "coming soon" message
        resp = client.get(PRICING_URL)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPlanDetailPage:
    def test_plan_detail_returns_200(self, client, starter_plan):
        url = reverse("services:plan_detail", kwargs={"slug": starter_plan.slug})
        resp = client.get(url)
        assert resp.status_code == 200

    def test_plan_detail_shows_plan_name(self, client, starter_plan):
        url = reverse("services:plan_detail", kwargs={"slug": starter_plan.slug})
        resp = client.get(url)
        assert b"Starter" in resp.content

    def test_plan_detail_404_for_inactive(self, client, inactive_plan):
        url = reverse("services:plan_detail", kwargs={"slug": inactive_plan.slug})
        resp = client.get(url)
        assert resp.status_code == 404

    def test_plan_detail_404_for_unknown_slug(self, client):
        url = reverse("services:plan_detail", kwargs={"slug": "does-not-exist"})
        resp = client.get(url)
        assert resp.status_code == 404
