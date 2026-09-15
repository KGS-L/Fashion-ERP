from django.urls import path

from .operation_views import (
    ManufacturingOperationActionView,
    ManufacturingOperationDetailView,
    ManufacturingOperationListCreateView,
    WorkCenterDetailView,
    WorkCenterListCreateView,
)
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
    path("work-centers/", WorkCenterListCreateView.as_view(), name="work-center-list"),
    path("work-centers/<uuid:work_center_id>/", WorkCenterDetailView.as_view(), name="work-center-detail"),
    path("orders/", ManufacturingOrderListCreateView.as_view(), name="order-list"),
    path("orders/<uuid:manufacturing_order_id>/", ManufacturingOrderDetailView.as_view(), name="order-detail"),
    path("orders/<uuid:manufacturing_order_id>/actions/", ManufacturingOrderActionView.as_view(), name="order-action"),
    path("orders/<uuid:manufacturing_order_id>/reserve-materials/", ManufacturingMaterialReservationView.as_view(), name="order-reserve-materials"),
    path("orders/<uuid:manufacturing_order_id>/operations/", ManufacturingOperationListCreateView.as_view(), name="operation-list"),
    path("operations/<uuid:operation_id>/", ManufacturingOperationDetailView.as_view(), name="operation-detail"),
    path("operations/<uuid:operation_id>/actions/", ManufacturingOperationActionView.as_view(), name="operation-action"),
]
