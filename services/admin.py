"""Admin registration for the Services catalog."""

from django.contrib import admin

from .models import PlanFeature, ServicePlan


class PlanFeatureInline(admin.TabularInline):
    model = PlanFeature
    extra = 3
    fields = ("text", "is_included", "sort_order")


@admin.register(ServicePlan)
class ServicePlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price_monthly",
        "price_annual",
        "tier_key",
        "is_active",
        "is_featured",
        "sort_order",
    )
    list_editable = ("is_active", "is_featured", "sort_order")
    list_filter = ("is_active", "is_featured", "billing_period")
    search_fields = ("name", "tagline", "tier_key")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [PlanFeatureInline]
    fieldsets = (
        (
            None,
            {
                "fields": ("name", "slug", "tagline", "description", "tier_key", "sort_order"),
            },
        ),
        (
            "Pricing",
            {
                "fields": ("price_monthly", "price_annual", "billing_period"),
            },
        ),
        (
            "Stripe",
            {
                "fields": ("stripe_price_id_monthly", "stripe_price_id_annual"),
                "classes": ("collapse",),
            },
        ),
        (
            "Visibility",
            {
                "fields": ("is_active", "is_featured"),
            },
        ),
    )
