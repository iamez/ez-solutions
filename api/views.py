"""REST API views — versioned under /api/v1/."""

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from services.models import ServicePlan
from tickets.models import Ticket, TicketMessage, TicketPriority, TicketStatus

from .serializers import (
    MeSerializer,
    ServicePlanSerializer,
    TicketCreateSerializer,
    TicketMessageSerializer,
    TicketReplySerializer,
    TicketSerializer,
)


class TicketCreateThrottle(UserRateThrottle):
    scope = "ticket_create"


class JWTAuthThrottle(UserRateThrottle):
    scope = "jwt_auth"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthView(APIView):
    """Simple liveness probe — returns 200 when the app can handle requests."""

    permission_classes = [AllowAny]
    authentication_classes = []  # skip session/token lookup for speed

    @extend_schema(
        operation_id="health_check",
        responses={
            200: inline_serializer(
                name="HealthResponse",
                fields={"status": serializers.CharField()},
            )
        },
    )
    def get(self, request):
        return Response({"status": "ok"})


# ---------------------------------------------------------------------------
# Plans (public)
# ---------------------------------------------------------------------------


class PlanListView(generics.ListAPIView):
    """Return the active, ordered service plan catalog (paginated)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = ServicePlanSerializer

    def get_queryset(self):
        return ServicePlan.objects.filter(is_active=True).prefetch_related("features")


# ---------------------------------------------------------------------------
# Tickets (authenticated)
# ---------------------------------------------------------------------------


class TicketListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/tickets/ — list the authenticated user's tickets (paginated, newest first).
    POST /api/v1/tickets/ — open a new support ticket.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = TicketSerializer

    def get_throttles(self):
        if self.request.method == "POST":
            return [TicketCreateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        return self.request.user.tickets.prefetch_related("messages").all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TicketCreateSerializer
        return TicketSerializer

    @extend_schema(
        operation_id="v1_tickets_list",
        responses=TicketSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        operation_id="v1_tickets_create",
        request=TicketCreateSerializer,
        responses={201: TicketSerializer, 400: OpenApiResponse(description="Validation error")},
    )
    def create(self, request, *args, **kwargs):
        serializer = TicketCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        priority_map = {
            "low": TicketPriority.LOW,
            "normal": TicketPriority.NORMAL,
            "high": TicketPriority.HIGH,
            "urgent": TicketPriority.URGENT,
        }
        with transaction.atomic():
            ticket = Ticket.objects.create(
                user=request.user,
                subject=data["subject"],
                status=TicketStatus.OPEN,
                priority=priority_map.get(data.get("priority", "normal"), TicketPriority.NORMAL),
            )
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                body=data["body"],
                is_staff_reply=False,
            )
        out = TicketSerializer(ticket)
        return Response(out.data, status=status.HTTP_201_CREATED)


class TicketDetailView(APIView):
    """
    GET  /api/v1/tickets/{pk}/ — ticket detail + full message thread.
    Users can only access their own tickets.
    """

    permission_classes = [IsAuthenticated]

    def _get_ticket(self, request, pk):
        try:
            return Ticket.objects.prefetch_related("messages").get(pk=pk, user=request.user)
        except Ticket.DoesNotExist:
            return None

    @extend_schema(
        operation_id="v1_tickets_detail",
        responses={200: TicketSerializer, 404: OpenApiResponse(description="Not found")},
    )
    def get(self, request, pk):
        ticket = self._get_ticket(request, pk)
        if ticket is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(TicketSerializer(ticket).data)


class TicketReplyView(APIView):
    """
    POST /api/v1/tickets/{pk}/reply/ — append a reply to an open ticket.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="v1_tickets_reply",
        request=TicketReplySerializer,
        responses={
            201: TicketMessageSerializer,
            400: OpenApiResponse(description="Validation error or ticket closed"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def post(self, request, pk):
        try:
            ticket = Ticket.objects.get(pk=pk, user=request.user)
        except Ticket.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if not ticket.is_open:
            return Response(
                {"detail": "Cannot reply to a closed ticket."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TicketReplySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        msg = TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            body=serializer.validated_data["body"],
            is_staff_reply=False,
        )
        return Response(TicketMessageSerializer(msg).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Me (authenticated)
# ---------------------------------------------------------------------------


class MeView(APIView):
    """
    GET   /api/v1/me/ — current user profile + active subscription.
    PATCH /api/v1/me/ — update first_name / last_name.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="v1_me_retrieve", responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)

    @extend_schema(
        operation_id="v1_me_partial_update",
        request=inline_serializer(
            name="MePatchRequest",
            fields={
                "first_name": serializers.CharField(required=False),
                "last_name": serializers.CharField(required=False),
            },
        ),
        responses={200: MeSerializer, 400: OpenApiResponse(description="Invalid payload")},
    )
    def patch(self, request):
        allowed = {k: v for k, v in request.data.items() if k in ("first_name", "last_name")}
        if not allowed:
            return Response(
                {"detail": "Only first_name and last_name may be updated."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Validate values are strings within model max_length
        for field, value in allowed.items():
            if not isinstance(value, str):
                return Response(
                    {"detail": f"{field} must be a string."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if len(value) > 150:
                return Response(
                    {"detail": f"{field} must be at most 150 characters."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        for field, value in allowed.items():
            setattr(request.user, field, value)
        request.user.save(update_fields=list(allowed.keys()))
        return Response(MeSerializer(request.user).data)
