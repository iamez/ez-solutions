"""REST API URL configuration — all routes versioned under /api/v1/."""

from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    HealthView,
    JWTAuthThrottle,
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
    # API docs
    path("v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("v1/docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
    # JWT auth
    path("v1/auth/token/", TokenObtainPairView.as_view(throttle_classes=[JWTAuthThrottle]), name="token-obtain-pair"),
    path("v1/auth/token/refresh/", TokenRefreshView.as_view(throttle_classes=[JWTAuthThrottle]), name="token-refresh"),
    # v1 routes
    path("v1/me/", MeView.as_view(), name="me"),
    path("v1/plans/", PlanListView.as_view(), name="plan-list"),
    path("v1/tickets/", TicketListCreateView.as_view(), name="ticket-list"),
    path("v1/tickets/<int:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("v1/tickets/<int:pk>/reply/", TicketReplyView.as_view(), name="ticket-reply"),
]
