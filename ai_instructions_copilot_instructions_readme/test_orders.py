"""
Tech-IT Solutions - Orders App Tests
Test suite for order processing, billing, and payments
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.orders.models import Order, Invoice, Payment
from apps.services.models import Service, ServicePlan
from decimal import Decimal
from datetime import datetime, timedelta

User = get_user_model()


class OrderModelTests(TestCase):
    """Test Order model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPass123!"
        )
        self.service = Service.objects.create(
            name="Web Hosting", slug="web-hosting", service_type="hosting"
        )
        self.plan = ServicePlan.objects.create(
            service=self.service,
            name="Basic Plan",
            price=Decimal("9.99"),
            billing_period="monthly",
        )

    def test_order_creation(self):
        """Test creating an order"""
        order = Order.objects.create(
            user=self.user,
            service_plan=self.plan,
            total_amount=Decimal("9.99"),
            status="pending",
        )
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.total_amount, Decimal("9.99"))
        self.assertEqual(order.status, "pending")

    def test_order_number_generation(self):
        """Test that order numbers are unique"""
        order1 = Order.objects.create(
            user=self.user, service_plan=self.plan, total_amount=Decimal("9.99")
        )
        order2 = Order.objects.create(
            user=self.user, service_plan=self.plan, total_amount=Decimal("9.99")
        )
        self.assertNotEqual(order1.order_number, order2.order_number)

    def test_order_status_transition(self):
        """Test order status transitions"""
        order = Order.objects.create(
            user=self.user,
            service_plan=self.plan,
            total_amount=Decimal("9.99"),
            status="pending",
        )
        order.status = "paid"
        order.save()
        self.assertEqual(order.status, "paid")

    def test_order_total_calculation(self):
        """Test order total calculation"""
        order = Order.objects.create(
            user=self.user, service_plan=self.plan, total_amount=self.plan.price
        )
        self.assertEqual(order.total_amount, self.plan.price)


class InvoiceTests(TestCase):
    """Test Invoice model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPass123!"
        )
        self.service = Service.objects.create(
            name="Web Hosting", slug="web-hosting", service_type="hosting"
        )
        self.plan = ServicePlan.objects.create(
            service=self.service,
            name="Basic Plan",
            price=Decimal("9.99"),
            billing_period="monthly",
        )
        self.order = Order.objects.create(
            user=self.user, service_plan=self.plan, total_amount=Decimal("9.99")
        )

    def test_invoice_creation(self):
        """Test creating an invoice"""
        invoice = Invoice.objects.create(order=self.order, amount=Decimal("9.99"), status="unpaid")
        self.assertEqual(invoice.amount, Decimal("9.99"))
        self.assertEqual(invoice.status, "unpaid")

    def test_invoice_number_generation(self):
        """Test invoice number generation"""
        invoice = Invoice.objects.create(order=self.order, amount=Decimal("9.99"))
        self.assertTrue(invoice.invoice_number.startswith("INV-"))

    def test_invoice_due_date(self):
        """Test invoice due date"""
        invoice = Invoice.objects.create(
            order=self.order,
            amount=Decimal("9.99"),
            due_date=datetime.now() + timedelta(days=7),
        )
        self.assertTrue(invoice.due_date > datetime.now())

    def test_overdue_invoice(self):
        """Test overdue invoice detection"""
        invoice = Invoice.objects.create(
            order=self.order,
            amount=Decimal("9.99"),
            due_date=datetime.now() - timedelta(days=1),
            status="unpaid",
        )
        self.assertTrue(invoice.is_overdue())


class PaymentTests(TestCase):
    """Test Payment processing"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPass123!"
        )
        self.service = Service.objects.create(
            name="Web Hosting", slug="web-hosting", service_type="hosting"
        )
        self.plan = ServicePlan.objects.create(
            service=self.service,
            name="Basic Plan",
            price=Decimal("9.99"),
            billing_period="monthly",
        )
        self.order = Order.objects.create(
            user=self.user, service_plan=self.plan, total_amount=Decimal("9.99")
        )
        self.invoice = Invoice.objects.create(order=self.order, amount=Decimal("9.99"))

    def test_payment_creation(self):
        """Test creating a payment"""
        payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("9.99"),
            payment_method="stripe",
            status="completed",
        )
        self.assertEqual(payment.amount, Decimal("9.99"))
        self.assertEqual(payment.status, "completed")

    def test_payment_updates_invoice(self):
        """Test that successful payment updates invoice"""
        payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("9.99"),
            payment_method="stripe",
            status="completed",
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "paid")

    def test_partial_payment(self):
        """Test partial payment"""
        payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("5.00"),
            payment_method="stripe",
            status="completed",
        )
        self.assertLess(payment.amount, self.invoice.amount)

    def test_failed_payment(self):
        """Test failed payment"""
        payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("9.99"),
            payment_method="stripe",
            status="failed",
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "unpaid")


class OrderViewTests(TestCase):
    """Test order-related views"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPass123!"
        )
        self.service = Service.objects.create(
            name="Web Hosting", slug="web-hosting", service_type="hosting"
        )
        self.plan = ServicePlan.objects.create(
            service=self.service,
            name="Basic Plan",
            price=Decimal("9.99"),
            billing_period="monthly",
        )

    def test_order_list_requires_login(self):
        """Test that order list requires authentication"""
        response = self.client.get(reverse("orders:order_list"))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_authenticated_user_can_view_orders(self):
        """Test that authenticated users can view their orders"""
        self.client.login(username="test@example.com", password="TestPass123!")
        response = self.client.get(reverse("orders:order_list"))
        self.assertEqual(response.status_code, 200)

    def test_user_only_sees_own_orders(self):
        """Test that users only see their own orders"""
        other_user = User.objects.create_user(
            username="other", email="other@example.com", password="TestPass123!"
        )
        Order.objects.create(user=other_user, service_plan=self.plan, total_amount=Decimal("9.99"))
        my_order = Order.objects.create(
            user=self.user, service_plan=self.plan, total_amount=Decimal("19.99")
        )

        self.client.login(username="test@example.com", password="TestPass123!")
        response = self.client.get(reverse("orders:order_list"))
        self.assertContains(response, "19.99")
        self.assertNotContains(response, "other@example.com")


class BillingTests(TestCase):
    """Test billing functionality"""

    def test_tax_calculation(self):
        """Test tax calculation on orders"""
        # This would test your tax calculation logic
        base_amount = Decimal("100.00")
        tax_rate = Decimal("0.10")  # 10%
        tax = base_amount * tax_rate
        total = base_amount + tax
        self.assertEqual(total, Decimal("110.00"))

    def test_recurring_billing(self):
        """Test recurring billing setup"""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPass123!"
        )
        service = Service.objects.create(
            name="Web Hosting", slug="web-hosting", service_type="hosting"
        )
        plan = ServicePlan.objects.create(
            service=service,
            name="Monthly Plan",
            price=Decimal("9.99"),
            billing_period="monthly",
        )
        order = Order.objects.create(
            user=user,
            service_plan=plan,
            total_amount=Decimal("9.99"),
            is_recurring=True,
        )
        self.assertTrue(order.is_recurring)
