"""URL configuration for EZ Solutions."""

from decouple import config
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from health_check.checks import Database
from health_check.contrib.celery import Ping as CeleryPing
from health_check.contrib.redis import Redis as RedisCheck
from health_check.views import HealthCheckView
from redis.asyncio import Redis as RedisClient

from home.sitemaps import PricingSitemap, StaticSitemap

sitemaps = {
    "static": StaticSitemap,
    "pricing": PricingSitemap,
}

urlpatterns = [
    # Admin
    path(config("ADMIN_URL", default="admin/"), admin.site.urls),
    # Infrastructure health endpoint (DB + Redis + Celery worker ping)
    # django-health-check 4.x: checks is a list of (Class, kwargs_dict) tuples,
    # or plain class references for zero-arg checks.
    path(
        "ht/",
        HealthCheckView.as_view(
            checks=[
                Database,
                (
                    RedisCheck,
                    {
                        "client": RedisClient.from_url(
                            config("REDIS_URL", default="redis://localhost:6379/0")
                        )
                    },
                ),
                CeleryPing,
            ]
        ),
        name="health-check",
    ),
    # Sitemap
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
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
