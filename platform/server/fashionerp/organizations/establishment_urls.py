from django.urls import path

from .views import EstablishmentDetailView, EstablishmentListView


app_name = "establishments"

urlpatterns = [
    path("", EstablishmentListView.as_view(), name="list"),
    path(
        "<uuid:establishment_id>/",
        EstablishmentDetailView.as_view(),
        name="detail",
    ),
]
