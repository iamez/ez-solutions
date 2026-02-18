"""DRF serializers for the public / authenticated REST API."""

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from orders.models import Subscription
from services.models import ServicePlan
from tickets.models import Ticket, TicketMessage

User = get_user_model()


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


class ServicePlanSerializer(serializers.ModelSerializer):
    """Read-only serializer for the pricing/plan catalog."""

    annual_savings = serializers.SerializerMethodField()

    class Meta:
        model = ServicePlan
        fields = [
            "id",
            "name",
            "slug",
            "tagline",
            "price_monthly",
            "price_annual",
            "billing_period",
            "tier_key",
            "is_featured",
            "sort_order",
            "annual_savings",
        ]
        read_only_fields = fields

    def get_annual_savings(self, obj) -> str | None:
        """Dollar amount saved by paying annually vs 12× monthly."""
        if obj.price_annual is not None:
            saved = (obj.price_monthly * 12) - obj.price_annual
            if saved > 0:
                return str(saved)
        return None


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------


class TicketMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source="sender.email", read_only=True)

    class Meta:
        model = TicketMessage
        fields = ["id", "sender_email", "body", "is_staff_reply", "created_at"]
        read_only_fields = fields


class TicketSerializer(serializers.ModelSerializer):
    """Full ticket detail including message thread."""

    messages = TicketMessageSerializer(many=True, read_only=True)
    message_count = serializers.IntegerField(read_only=True)
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "reference_short",
            "subject",
            "status",
            "priority",
            "is_open",
            "message_count",
            "messages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reference_short",
            "status",
            "is_open",
            "message_count",
            "messages",
            "created_at",
            "updated_at",
        ]


class TicketCreateSerializer(serializers.Serializer):
    """Payload for opening a new support ticket."""

    subject = serializers.CharField(max_length=200)
    body = serializers.CharField(max_length=10000)
    priority = serializers.ChoiceField(
        choices=["low", "normal", "high", "urgent"],
        default="normal",
    )


class TicketReplySerializer(serializers.Serializer):
    """Payload for adding a reply to an existing ticket."""

    body = serializers.CharField(max_length=10000)


# ---------------------------------------------------------------------------
# User / Me
# ---------------------------------------------------------------------------


class SubscriptionSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)
    days_until_renewal = serializers.IntegerField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "stripe_subscription_id",
            "status",
            "is_active",
            "current_period_end",
            "days_until_renewal",
            "cancel_at_period_end",
        ]


class MeSerializer(serializers.ModelSerializer):
    """Current authenticated user profile."""

    subscription = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "subscription_tier",
            "date_joined",
            "subscription",
        ]
        read_only_fields = ["id", "email", "subscription_tier", "date_joined", "subscription"]

    @extend_schema_field(SubscriptionSerializer(allow_null=True))
    def get_subscription(self, user):
        customer = getattr(user, "stripe_customer", None)
        if customer is None:
            return None
        sub = customer.get_active_subscription()
        if sub is None:
            return None
        return SubscriptionSerializer(sub).data
