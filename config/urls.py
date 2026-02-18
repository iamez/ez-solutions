"""URL configuration for EZ Solutions."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from decouple import config

from .health import health_check

urlpatterns = [
    # Admin
    path(config("ADMIN_URL", default="admin/"), admin.site.urls),
    # Infrastructure health endpoint
    path("ht/", health_check, name="health-check"),
    # Public pages
    path("", include("home.urls", namespace="home")),
    # Allauth (login, logout, register, email verification, password reset)
    path("accounts/", include("allauth.urls")),
    # Authenticated user area
    path("dashboard/", include("users.urls", namespace="users")),
    # REST API
    path("api/", include("api.urls", namespace="api")),
    # Services catalog (pricing)
    path("", include("services.urls", namespace="services")),
    # Billing & Stripe
    path("", include("orders.urls", namespace="orders")),
    # Support tickets
    path("tickets/", include("tickets.urls", namespace="tickets")),
    # Notification preferences & unsubscribe
    path("notifications/", include("notifications.urls", namespace="notifications")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Django Debug Toolbar
    import debug_toolbar  # noqa: PLC0415

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
