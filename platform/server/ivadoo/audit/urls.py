from django.urls import path

from .views import AuditEventListView


app_name = "audit"

urlpatterns = [
    path("events/", AuditEventListView.as_view(), name="event-list"),
]
