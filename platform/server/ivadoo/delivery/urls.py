from django.urls import path

from .views import (
    DeliveryActionView,
    DeliveryBalanceView,
    DeliveryDetailView,
    DeliveryListCreateView,
    DeliveryReturnDetailView,
    DeliveryReturnListCreateView,
)


app_name = "delivery"

urlpatterns = [
    path("deliveries/", DeliveryListCreateView.as_view(), name="delivery-list"),
    path("deliveries/<uuid:delivery_id>/", DeliveryDetailView.as_view(), name="delivery-detail"),
    path("deliveries/<uuid:delivery_id>/actions/<str:action>/", DeliveryActionView.as_view(), name="delivery-action"),
    path("returns/", DeliveryReturnListCreateView.as_view(), name="return-list"),
    path("returns/<uuid:return_id>/", DeliveryReturnDetailView.as_view(), name="return-detail"),
    path("orders/<uuid:order_id>/balance/", DeliveryBalanceView.as_view(), name="order-delivery-balance"),
]
