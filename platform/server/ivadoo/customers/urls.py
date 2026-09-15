from django.urls import path

from .views import CustomerDetailView, CustomerListView


app_name = "customers"

urlpatterns = [
    path("", CustomerListView.as_view(), name="list"),
    path("<uuid:customer_id>/", CustomerDetailView.as_view(), name="detail"),
]
