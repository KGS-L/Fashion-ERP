from django.urls import path

from .views import OrganizationDetailView, OrganizationListView


app_name = "organizations"

urlpatterns = [
    path("", OrganizationListView.as_view(), name="list"),
    path("<uuid:organization_id>/", OrganizationDetailView.as_view(), name="detail"),
]
