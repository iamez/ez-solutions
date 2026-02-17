# customer_experience/legal_pages/views.py
"""
Legal Pages Views - Terms of Service, Privacy Policy, etc.
"""

from django.shortcuts import render
from django.views.generic import TemplateView


class TermsOfServiceView(TemplateView):
    """Terms of Service page"""

    template_name = "legal/terms_of_service.html"


class PrivacyPolicyView(TemplateView):
    """Privacy Policy page"""

    template_name = "legal/privacy_policy.html"


class CookiePolicyView(TemplateView):
    """Cookie Policy page"""

    template_name = "legal/cookie_policy.html"


class AcceptableUsePolicyView(TemplateView):
    """Acceptable Use Policy page"""

    template_name = "legal/acceptable_use.html"


class SLAView(TemplateView):
    """Service Level Agreement page"""

    template_name = "legal/sla.html"


# URLs configuration
"""
# legal/urls.py
from django.urls import path
from . import views

app_name = 'legal'

urlpatterns = [
    path('terms/', views.TermsOfServiceView.as_view(), name='terms'),
    path('privacy/', views.PrivacyPolicyView.as_view(), name='privacy'),
    path('cookies/', views.CookiePolicyView.as_view(), name='cookies'),
    path('acceptable-use/', views.AcceptableUsePolicyView.as_view(), name='acceptable_use'),
    path('sla/', views.SLAView.as_view(), name='sla'),
]
"""
