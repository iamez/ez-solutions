"""URL routing for Support Tickets."""

from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("new/", views.ticket_create, name="create"),
    path("staff/", views.staff_ticket_list, name="staff_list"),
    path("staff/<int:pk>/", views.staff_ticket_detail, name="staff_detail"),
    path("<int:pk>/", views.ticket_detail, name="detail"),
]
