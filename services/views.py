"""Services catalog views."""

from django.shortcuts import get_object_or_404, render

from .models import ServicePlan


def pricing(request):
    """Public pricing/plans page."""
    plans = ServicePlan.objects.filter(is_active=True).prefetch_related("features")
    return render(request, "services/pricing.html", {"plans": plans})


def plan_detail(request, slug):
    """Detail page for a single plan (used for SEO landing pages)."""
    plan = get_object_or_404(ServicePlan, slug=slug, is_active=True)
    return render(request, "services/plan_detail.html", {"plan": plan})
