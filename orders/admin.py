"""Admin registration for billing / orders."""

from django.contrib import admin

from .models import Customer, Order, PaymentEvent, ProvisioningJob, Subscription, VPSInstance


class SubscriptionInline(admin.TabularInline):
    model = Subscription
    extra = 0
    readonly_fields = (
        "stripe_subscription_id",
        "stripe_price_id",
        "status",
        "current_period_end",
        "created_at",
    )
    can_delete = False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("user", "stripe_customer_id", "created_at")
    search_fields = ("user__email", "stripe_customer_id")
    readonly_fields = ("stripe_customer_id", "created_at")
    inlines = [SubscriptionInline]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "stripe_subscription_id",
        "get_user_email",
        "status",
        "current_period_end",
        "cancel_at_period_end",
        "updated_at",
    )
    list_filter = ("status", "cancel_at_period_end")
    search_fields = ("stripe_subscription_id", "customer__user__email")
    readonly_fields = ("stripe_subscription_id", "stripe_price_id", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("customer__user")

    @admin.display(description="User Email")
    def get_user_email(self, obj):
        return obj.customer.user.email


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ("stripe_event_id", "event_type", "processed_at")
    list_filter = ("event_type",)
    search_fields = ("stripe_event_id", "event_type")
    readonly_fields = ("stripe_event_id", "event_type", "processed_at", "payload")
    list_per_page = 25

    def has_add_permission(self, request):
        return False  # events are logged by webhooks only


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "service_plan",
        "status",
        "amount_total",
        "currency",
        "created_at",
    )
    list_filter = ("status", "currency", "created_at")
    search_fields = (
        "customer__user__email",
        "service_plan__name",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProvisioningJob)
class ProvisioningJobAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider", "status", "external_id", "created_at")
    list_filter = ("provider", "status", "created_at")
    search_fields = ("external_id", "order__customer__user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(VPSInstance)
class VPSInstanceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "hostname",
        "customer",
        "status",
        "ip_address",
        "proxmox_vmid",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("hostname", "ip_address", "customer__user__email", "proxmox_vmid")
    readonly_fields = ("created_at", "updated_at")
