"""REST API URL configuration — all routes versioned under /api/v1/."""

from django.urls import path

from .views import (
    HealthView,
    MeView,
    PlanListView,
    TicketDetailView,
    TicketListCreateView,
    TicketReplyView,
)

app_name = "api"

urlpatterns = [
    # Liveness / readiness probe
    path("health/", HealthView.as_view(), name="health"),
    # v1 routes
    path("v1/me/", MeView.as_view(), name="me"),
    path("v1/plans/", PlanListView.as_view(), name="plan-list"),
    path("v1/tickets/", TicketListCreateView.as_view(), name="ticket-list"),
    path("v1/tickets/<int:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("v1/tickets/<int:pk>/reply/", TicketReplyView.as_view(), name="ticket-reply"),
]
