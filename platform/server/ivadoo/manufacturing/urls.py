from django.urls import path

from .views import (
    BillOfMaterialsActionView,
    BillOfMaterialsDetailView,
    BillOfMaterialsListCreateView,
    ManufacturingMaterialReservationView,
    ManufacturingOrderActionView,
    ManufacturingOrderDetailView,
    ManufacturingOrderListCreateView,
)


app_name = "manufacturing"

urlpatterns = [
    path("boms/", BillOfMaterialsListCreateView.as_view(), name="bom-list"),
    path("boms/<uuid:bom_id>/", BillOfMaterialsDetailView.as_view(), name="bom-detail"),
    path("boms/<uuid:bom_id>/actions/", BillOfMaterialsActionView.as_view(), name="bom-action"),
    path("orders/", ManufacturingOrderListCreateView.as_view(), name="order-list"),
    path("orders/<uuid:manufacturing_order_id>/", ManufacturingOrderDetailView.as_view(), name="order-detail"),
    path("orders/<uuid:manufacturing_order_id>/actions/", ManufacturingOrderActionView.as_view(), name="order-action"),
    path("orders/<uuid:manufacturing_order_id>/reserve-materials/", ManufacturingMaterialReservationView.as_view(), name="order-reserve-materials"),
]
