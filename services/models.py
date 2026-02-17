"""Services catalog models — plan tiers and their features."""

from decimal import Decimal

from django.db import models
from django.utils.text import slugify


class BillingPeriod(models.TextChoices):
    MONTHLY = "monthly", "Monthly"
    ANNUAL = "annual", "Annual"


class ServicePlan(models.Model):
    """A purchasable service plan (e.g. Starter, Professional, Enterprise)."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    tagline = models.CharField(max_length=200, blank=True, help_text="Short marketing blurb")
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(
        max_digits=8, decimal_places=2, help_text="Price in USD per month"
    )
    price_annual = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Annual price (leave blank if same as monthly × 12)",
    )
    billing_period = models.CharField(
        max_length=20,
        choices=BillingPeriod.choices,
        default=BillingPeriod.MONTHLY,
    )
    stripe_price_id_monthly = models.CharField(
        max_length=100,
        blank=True,
        help_text="Stripe Price ID for the monthly price object",
    )
    stripe_price_id_annual = models.CharField(
        max_length=100,
        blank=True,
        help_text="Stripe Price ID for the annual price object",
    )
    # Maps to users.User.subscription_tier value
    tier_key = models.CharField(
        max_length=50,
        blank=True,
        help_text="Matches subscription_tier value on User (e.g. starter, professional)",
    )
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Highlight on pricing page")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "price_monthly"]
        verbose_name = "Service Plan"
        verbose_name_plural = "Service Plans"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def annual_savings(self) -> str | None:
        """Human-readable annual savings string, e.g. '$24/yr'."""
        if self.price_annual:
            monthly_total = Decimal(str(self.price_monthly)) * 12
            saved = monthly_total - Decimal(str(self.price_annual))
            if saved > 0:
                return f"Save ${saved:.0f}/yr"
        return None


class PlanFeature(models.Model):
    """A bullet-point feature line shown on the pricing card."""

    plan = models.ForeignKey(ServicePlan, on_delete=models.CASCADE, related_name="features")
    text = models.CharField(max_length=200)
    is_included = models.BooleanField(default=True, help_text="✓ included vs ✗ not included")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Plan Feature"
        verbose_name_plural = "Plan Features"

    def __str__(self) -> str:
        prefix = "✓" if self.is_included else "✗"
        return f"{prefix} {self.plan.name}: {self.text}"
