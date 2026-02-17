"""URL routing for the Services catalog."""

from django.urls import path

from . import views

app_name = "services"

urlpatterns = [
    path("pricing/", views.pricing, name="pricing"),
    path("pricing/<slug:slug>/", views.plan_detail, name="plan_detail"),
]
