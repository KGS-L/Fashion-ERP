from django.urls import path

from .views import (
    ReservationConsumeView,
    ReservationReleaseView,
    ReservationStartProductionView,
    StockLocationDetailView,
    StockLocationListCreateView,
    StockLotDetailView,
    StockLotListCreateView,
    StockMovementApplyView,
    StockMovementListView,
    StockPositionListView,
    StockReservationListCreateView,
    WarehouseDetailView,
    WarehouseListCreateView,
)


app_name = "inventory"

urlpatterns = [
    path("warehouses/", WarehouseListCreateView.as_view(), name="warehouse-list"),
    path("warehouses/<uuid:warehouse_id>/", WarehouseDetailView.as_view(), name="warehouse-detail"),
    path("locations/", StockLocationListCreateView.as_view(), name="location-list"),
    path("locations/<uuid:location_id>/", StockLocationDetailView.as_view(), name="location-detail"),
    path("positions/", StockPositionListView.as_view(), name="position-list"),
    path("lots/", StockLotListCreateView.as_view(), name="lot-list"),
    path("lots/<uuid:lot_id>/", StockLotDetailView.as_view(), name="lot-detail"),
    path("movements/", StockMovementListView.as_view(), name="movement-list"),
    path("movements/apply/", StockMovementApplyView.as_view(), name="movement-apply"),
    path("reservations/", StockReservationListCreateView.as_view(), name="reservation-list"),
    path("reservations/<uuid:reservation_id>/release/", ReservationReleaseView.as_view(), name="reservation-release"),
    path("reservations/<uuid:reservation_id>/start-production/", ReservationStartProductionView.as_view(), name="reservation-start-production"),
    path("reservations/<uuid:reservation_id>/consume/", ReservationConsumeView.as_view(), name="reservation-consume"),
]
