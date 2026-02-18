"""URL routing for billing / orders."""

from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    # Authenticated billing area
    path("billing/", views.billing, name="billing"),
    path("billing/history/", views.order_history, name="order_history"),
    path("billing/portal/", views.billing_portal, name="billing_portal"),
    # Stripe Checkout — initiated from pricing page
    path("billing/checkout/<slug:plan_slug>/", views.create_checkout_session, name="checkout"),
    # Stripe webhook (no auth, signature-verified instead)
    path("webhooks/stripe/", views.stripe_webhook, name="stripe_webhook"),
]
