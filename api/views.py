"""REST API views — versioned under /api/v1/."""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
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

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthView(APIView):
    """Simple liveness probe — returns 200 when the app can handle requests."""

    permission_classes = [AllowAny]
    authentication_classes = []  # skip session/token lookup for speed

    def get(self, request):
        return Response({"status": "ok"})


# ---------------------------------------------------------------------------
# Plans (public)
# ---------------------------------------------------------------------------


class PlanListView(APIView):
    """Return the active, ordered service plan catalog."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        plans = ServicePlan.objects.filter(is_active=True)
        serializer = ServicePlanSerializer(plans, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Tickets (authenticated)
# ---------------------------------------------------------------------------


class TicketListCreateView(APIView):
    """
    GET  /api/v1/tickets/ — list the authenticated user's tickets (newest first).
    POST /api/v1/tickets/ — open a new support ticket.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tickets = request.user.tickets.prefetch_related("messages").all()
        serializer = TicketSerializer(tickets, many=True)
        return Response(serializer.data)

    def post(self, request):
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

    def get(self, request):
        return Response(MeSerializer(request.user).data)

    def patch(self, request):
        allowed = {k: v for k, v in request.data.items() if k in ("first_name", "last_name")}
        if not allowed:
            return Response(
                {"detail": "Only first_name and last_name may be updated."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for field, value in allowed.items():
            setattr(request.user, field, value)
        request.user.save(update_fields=list(allowed.keys()))
        return Response(MeSerializer(request.user).data)
