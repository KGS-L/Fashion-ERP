from django.urls import path

from .views import MeasurementSetDetailView, MeasurementSetListCreateView


app_name = "measurements"

urlpatterns = [
    path("", MeasurementSetListCreateView.as_view(), name="list-create"),
    path("<uuid:measurement_set_id>/", MeasurementSetDetailView.as_view(), name="detail"),
]
