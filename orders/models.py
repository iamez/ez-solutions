"""Billing / orders models — Stripe customer, subscription, and webhook event log."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Customer(models.Model):
    """One-to-one link between a Django User and a Stripe Customer object."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stripe_customer",
    )
    stripe_customer_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Stripe Customer"
        verbose_name_plural = "Stripe Customers"

    def __str__(self) -> str:
        return f"{self.user.email} → {self.stripe_customer_id}"

    def get_active_subscription(self):
        """Return the first active/trialing/past_due subscription, or None."""
        return self.subscriptions.filter(
            status__in=[
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIALING,
                SubscriptionStatus.PAST_DUE,
            ]
        ).first()


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PAST_DUE = "past_due", "Past Due"
    UNPAID = "unpaid", "Unpaid"
    CANCELED = "canceled", "Canceled"
    INCOMPLETE = "incomplete", "Incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired", "Incomplete Expired"
    TRIALING = "trialing", "Trialing"
    PAUSED = "paused", "Paused"


class Subscription(models.Model):
    """Mirrors a Stripe Subscription object; kept in sync via webhook."""

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    stripe_subscription_id = models.CharField(max_length=100, unique=True)
    stripe_price_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=30,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.INCOMPLETE,
        db_index=True,
    )
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.stripe_subscription_id} ({self.status})"

    @property
    def is_active(self) -> bool:
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)

    @property
    def is_past_due(self) -> bool:
        return self.status == SubscriptionStatus.PAST_DUE

    @property
    def days_until_renewal(self) -> int | None:
        if self.current_period_end:
            delta = self.current_period_end - timezone.now()
            return max(0, delta.days)
        return None


class EventStatus(models.TextChoices):
    RECEIVED = "received", "Received"
    PROCESSING = "processing", "Processing"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class PaymentEvent(models.Model):
    """Idempotency log — records every processed Stripe webhook event ID."""

    stripe_event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=100, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        default=EventStatus.RECEIVED,
        db_index=True,
    )
    error_message = models.TextField(blank=True, default="")
    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField(default=dict, help_text="Full event payload for audit trail")

    class Meta:
        verbose_name = "Payment Event"
        verbose_name_plural = "Payment Events"
        ordering = ["-received_at"]

    def __str__(self) -> str:
        return f"{self.event_type} — {self.stripe_event_id} [{self.status}]"


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    CANCELED = "canceled", "Canceled"
    FAILED = "failed", "Failed"


class ProvisioningStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    PROVISIONING = "provisioning", "Provisioning"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class VPSInstanceStatus(models.TextChoices):
    PROVISIONING = "provisioning", "Provisioning"
    RUNNING = "running", "Running"
    STOPPED = "stopped", "Stopped"
    SUSPENDED = "suspended", "Suspended"
    TERMINATED = "terminated", "Terminated"
    ERROR = "error", "Error"


class Order(models.Model):
    """Commercial order record tying customer, plan, and payment references."""

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders")
    service_plan = models.ForeignKey("services.ServicePlan", on_delete=models.PROTECT)
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )
    stripe_checkout_session_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
    )
    stripe_payment_intent_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
    )
    amount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="usd")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.pk} ({self.status})"


class ProvisioningJob(models.Model):
    """Tracks async infrastructure provisioning progress per order."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="provisioning_jobs")
    provider = models.CharField(max_length=50, default="proxmox")
    status = models.CharField(
        max_length=20,
        choices=ProvisioningStatus.choices,
        default=ProvisioningStatus.QUEUED,
        db_index=True,
    )
    external_id = models.CharField(max_length=100, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ProvisioningJob #{self.pk} ({self.status})"


class VPSInstance(models.Model):
    """Represents a provisioned VPS instance linked to a customer order flow."""

    provisioning_job = models.OneToOneField(
        ProvisioningJob,
        on_delete=models.CASCADE,
        related_name="vps_instance",
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="vps_instances")
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vps_instances",
    )
    hostname = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    proxmox_vmid = models.PositiveIntegerField(null=True, blank=True, unique=True)
    os_template = models.CharField(max_length=100, blank=True)
    cpu_cores = models.PositiveSmallIntegerField(default=1)
    ram_mb = models.PositiveIntegerField(default=1024)
    disk_gb = models.PositiveIntegerField(default=20)
    status = models.CharField(
        max_length=20,
        choices=VPSInstanceStatus.choices,
        default=VPSInstanceStatus.PROVISIONING,
        db_index=True,
    )
    credentials_ref = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.hostname} ({self.status})"
