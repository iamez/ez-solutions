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


class PaymentEvent(models.Model):
    """Idempotency log — records every processed Stripe webhook event ID."""

    stripe_event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict, help_text="Full event payload for audit trail")

    class Meta:
        verbose_name = "Payment Event"
        verbose_name_plural = "Payment Events"
        ordering = ["-processed_at"]

    def __str__(self) -> str:
        return f"{self.event_type} — {self.stripe_event_id}"
