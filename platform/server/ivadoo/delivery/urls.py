from django.urls import path

from .views import DeliveryActionView, DeliveryDetailView, DeliveryListCreateView


app_name = "delivery"

urlpatterns = [
    path("deliveries/", DeliveryListCreateView.as_view(), name="delivery-list"),
    path("deliveries/<uuid:delivery_id>/", DeliveryDetailView.as_view(), name="delivery-detail"),
    path("deliveries/<uuid:delivery_id>/actions/<str:action>/", DeliveryActionView.as_view(), name="delivery-action"),
]
