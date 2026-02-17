from django.shortcuts import render

from services.models import ServicePlan


def index(request):
    """Public landing page — passes active service plans for the pricing teaser."""
    plans = ServicePlan.objects.filter(is_active=True).prefetch_related("features")[:3]
    return render(request, "users/home.html", {"plans": plans})


def about(request):
    """About page."""
    return render(request, "home/about.html")
