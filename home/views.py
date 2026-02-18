from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control

from services.models import ServicePlan


def index(request):
    """Public landing page — passes active service plans for the pricing teaser."""
    plans = ServicePlan.objects.filter(is_active=True).prefetch_related("features")[:3]
    return render(request, "home/landing.html", {"plans": plans})


def about(request):
    """About page."""
    return render(request, "home/about.html")


@cache_control(max_age=86400)
def robots_txt(request):
    """Serve /robots.txt telling crawlers what to index."""
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /dashboard/",
        "Disallow: /tickets/",
        "Disallow: /api/",
        "",
        "Sitemap: https://ez-solutions.com/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
