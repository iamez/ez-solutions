"""URL routes for notification preferences."""

from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("preferences/", views.notification_preferences, name="preferences"),
    path("unsubscribe/<str:token>/", views.unsubscribe, name="unsubscribe"),
]
