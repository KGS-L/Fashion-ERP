from django.urls import path

from .views import CompanyDetailView, CompanyListView


app_name = "companies"

urlpatterns = [
    path("", CompanyListView.as_view(), name="list"),
    path("<uuid:company_id>/", CompanyDetailView.as_view(), name="detail"),
]
