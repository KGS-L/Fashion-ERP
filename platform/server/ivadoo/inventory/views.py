from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ivadoo.audit.services import audit_snapshot, record_audit_event
from ivadoo.authorization.services import authorized_company_ids, has_permission

from .models import StockLocation, StockLot, StockMovement, StockPosition, StockReservation, Warehouse
from .serializers import (
    StockLocationSerializer,
    StockLotSerializer,
    StockMovementCreateSerializer,
    StockMovementSerializer,
    StockPositionSerializer,
    StockReservationCreateSerializer,
    StockReservationSerializer,
    WarehouseSerializer,
)
from .services import (
    apply_stock_movement,
    consume_reservation,
    create_lot_with_opening_stock,
    release_reservation,
    reserve_stock,
    start_reservation_production,
)


def _raise_service_validation(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def scoped_warehouses(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return Warehouse.objects.none()
    return Warehouse.objects.filter(
        organization_id=user.organization_id,
        company_id__in=company_ids,
    ).select_related("company", "establishment")


class WarehouseListCreateView(generics.ListCreateAPIView):
    queryset = Warehouse.objects.none()
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "establishment_id", "is_active")
    search_fields = ("code", "name")
    ordering_fields = ("name", "code", "created_at", "updated_at")
    ordering = ("name",)

    def get_queryset(self):
        return scoped_warehouses(self.request.user, "inventory.stock.view")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        establishment = serializer.validated_data.get("establishment")
        if not has_permission(
            self.request.user,
            "inventory.stock.manage",
            company=company,
            establishment=establishment,
        ):
            raise PermissionDenied("You cannot manage warehouses in this scope.")
        with transaction.atomic():
            warehouse = serializer.save(organization=self.request.user.organization)
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="inventory.warehouse.create",
                object_instance=warehouse,
                after=audit_snapshot(warehouse),
                request=self.request,
            )


class WarehouseDetailView(generics.RetrieveUpdateAPIView):
    queryset = Warehouse.objects.none()
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "warehouse_id"

    def get_queryset(self):
        permission = "inventory.stock.view" if self.request.method == "GET" else "inventory.stock.manage"
        return scoped_warehouses(self.request.user, permission)

    def perform_update(self, serializer):
        company = serializer.validated_data.get("company", serializer.instance.company)
        establishment = serializer.validated_data.get("establishment", serializer.instance.establishment)
        if not has_permission(
            self.request.user,
            "inventory.stock.manage",
            company=company,
            establishment=establishment,
        ):
            raise PermissionDenied("You cannot manage warehouses in this scope.")
        before = audit_snapshot(serializer.instance)
        warehouse = serializer.save()
        record_audit_event(
            organization=self.request.user.organization,
            actor=self.request.user,
            action="inventory.warehouse.update",
            object_instance=warehouse,
            before=before,
            after=audit_snapshot(warehouse),
            request=self.request,
        )


class StockLocationListCreateView(generics.ListCreateAPIView):
    queryset = StockLocation.objects.none()
    serializer_class = StockLocationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("warehouse_id", "kind", "is_active")
    search_fields = ("code", "name")
    ordering_fields = ("code", "name", "created_at")
    ordering = ("warehouse__name", "code")

    def get_queryset(self):
        warehouses = scoped_warehouses(self.request.user, "inventory.stock.view")
        return StockLocation.objects.filter(warehouse__in=warehouses).select_related(
            "warehouse", "warehouse__company", "warehouse__establishment", "parent"
        )

    def perform_create(self, serializer):
        warehouse = serializer.validated_data["warehouse"]
        if not has_permission(
            self.request.user,
            "inventory.stock.manage",
            company=warehouse.company,
            establishment=warehouse.establishment,
        ):
            raise PermissionDenied("You cannot manage stock locations in this scope.")
        location = serializer.save()
        record_audit_event(
            organization=self.request.user.organization,
            actor=self.request.user,
            action="inventory.location.create",
            object_instance=location,
            after=audit_snapshot(location),
            request=self.request,
        )


class StockLocationDetailView(generics.RetrieveUpdateAPIView):
    queryset = StockLocation.objects.none()
    serializer_class = StockLocationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "location_id"

    def get_queryset(self):
        permission = "inventory.stock.view" if self.request.method == "GET" else "inventory.stock.manage"
        warehouses = scoped_warehouses(self.request.user, permission)
        return StockLocation.objects.filter(warehouse__in=warehouses).select_related("warehouse", "parent")

    def perform_update(self, serializer):
        warehouse = serializer.validated_data.get("warehouse", serializer.instance.warehouse)
        if not has_permission(
            self.request.user,
            "inventory.stock.manage",
            company=warehouse.company,
            establishment=warehouse.establishment,
        ):
            raise PermissionDenied("You cannot manage stock locations in this scope.")
        before = audit_snapshot(serializer.instance)
        location = serializer.save()
        record_audit_event(
            organization=self.request.user.organization,
            actor=self.request.user,
            action="inventory.location.update",
            object_instance=location,
            before=before,
            after=audit_snapshot(location),
            request=self.request,
        )


class StockPositionListView(generics.ListAPIView):
    queryset = StockPosition.objects.none()
    serializer_class = StockPositionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("warehouse_id", "location_id", "product_id", "product_variant_id", "unit_id")
    ordering_fields = ("updated_at", "quantity_available", "quantity_reserved")

    def get_queryset(self):
        warehouse_ids = scoped_warehouses(self.request.user, "inventory.stock.view").values_list("id", flat=True)
        return StockPosition.objects.filter(
            organization_id=self.request.user.organization_id,
            warehouse_id__in=warehouse_ids,
        ).select_related("warehouse", "location", "product", "product_variant", "unit")


class StockLotListCreateView(generics.ListCreateAPIView):
    queryset = StockLot.objects.none()
    serializer_class = StockLotSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("warehouse_id", "location_id", "product_id", "product_variant_id", "kind", "status")
    search_fields = ("code", "origin", "supplier_reference")
    ordering_fields = ("code", "created_at", "updated_at", "remaining_quantity")
    ordering = ("code",)

    def get_queryset(self):
        warehouse_ids = scoped_warehouses(self.request.user, "inventory.stock.view").values_list("id", flat=True)
        return StockLot.objects.filter(
            organization_id=self.request.user.organization_id,
            warehouse_id__in=warehouse_ids,
        ).select_related("warehouse", "location", "product", "product_variant", "unit")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        opening_quantity = data.pop("opening_quantity", None)
        if opening_quantity is None:
            raise ValidationError({"opening_quantity": "Opening quantity is required when creating a lot."})
        warehouse = data["warehouse"]
        if not has_permission(
            request.user,
            "inventory.stock.manage",
            company=warehouse.company,
            establishment=warehouse.establishment,
        ):
            raise PermissionDenied("You cannot manage stock lots in this scope.")
        try:
            lot, _ = create_lot_with_opening_stock(
                organization=request.user.organization,
                actor=request.user,
                opening_quantity=opening_quantity,
                request=request,
                **data,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        output = self.get_serializer(lot)
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)


class StockLotDetailView(generics.RetrieveUpdateAPIView):
    queryset = StockLot.objects.none()
    serializer_class = StockLotSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "lot_id"

    def get_queryset(self):
        permission = "inventory.stock.view" if self.request.method == "GET" else "inventory.stock.manage"
        warehouse_ids = scoped_warehouses(self.request.user, permission).values_list("id", flat=True)
        return StockLot.objects.filter(
            organization_id=self.request.user.organization_id,
            warehouse_id__in=warehouse_ids,
        ).select_related("warehouse", "location", "product", "product_variant", "unit")

    def perform_update(self, serializer):
        warehouse = serializer.validated_data.get("warehouse", serializer.instance.warehouse)
        if not has_permission(
            self.request.user,
            "inventory.stock.manage",
            company=warehouse.company,
            establishment=warehouse.establishment,
        ):
            raise PermissionDenied("You cannot manage stock lots in this scope.")
        before = audit_snapshot(serializer.instance)
        lot = serializer.save()
        record_audit_event(
            organization=self.request.user.organization,
            actor=self.request.user,
            action="inventory.lot.update",
            object_instance=lot,
            before=before,
            after=audit_snapshot(lot),
            request=self.request,
        )


class StockMovementListView(generics.ListAPIView):
    queryset = StockMovement.objects.none()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "movement_type", "product_id", "product_variant_id", "lot_id", "reference_type", "reference_id")
    ordering_fields = ("created_at", "quantity")
    ordering = ("-created_at",)

    def get_queryset(self):
        company_ids = authorized_company_ids(self.request.user, "inventory.stock.view")
        return StockMovement.objects.filter(
            organization_id=self.request.user.organization_id,
            company_id__in=company_ids,
        ).select_related("company", "source_location", "destination_location", "product", "product_variant", "unit", "lot")


@extend_schema(request=StockMovementCreateSerializer, responses={201: StockMovementSerializer})
class StockMovementApplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StockMovementCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        location = data.get("source_location") or data.get("destination_location")
        if location is None:
            raise ValidationError("At least one stock location is required.")
        warehouse = location.warehouse
        if not has_permission(
            request.user,
            "inventory.stock.manage",
            company=warehouse.company,
            establishment=warehouse.establishment,
        ):
            raise PermissionDenied("You cannot apply stock movements in this scope.")
        other = data.get("destination_location") if data.get("source_location") else None
        if other and not has_permission(
            request.user,
            "inventory.stock.manage",
            company=other.warehouse.company,
            establishment=other.warehouse.establishment,
        ):
            raise PermissionDenied("You cannot apply stock movements in the destination scope.")
        try:
            movement = apply_stock_movement(
                organization=request.user.organization,
                actor=request.user,
                request=request,
                **data,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(StockMovementSerializer(movement).data, status=status.HTTP_201_CREATED)


class StockReservationListCreateView(generics.ListAPIView):
    queryset = StockReservation.objects.none()
    serializer_class = StockReservationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "warehouse_id", "location_id", "product_id", "order_id", "production_order_id", "status")
    ordering = ("-created_at",)

    def get_queryset(self):
        company_ids = authorized_company_ids(self.request.user, "inventory.stock.view")
        return StockReservation.objects.filter(
            organization_id=self.request.user.organization_id,
            company_id__in=company_ids,
        ).select_related("company", "warehouse", "location", "product", "product_variant", "unit", "lot", "order")

    @extend_schema(request=StockReservationCreateSerializer, responses={201: StockReservationSerializer})
    def post(self, request, *args, **kwargs):
        serializer = StockReservationCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        location = data["location"]
        if not has_permission(
            request.user,
            "inventory.stock.reserve",
            company=location.warehouse.company,
            establishment=location.warehouse.establishment,
        ):
            raise PermissionDenied("You cannot reserve stock in this scope.")
        try:
            reservation = reserve_stock(
                organization=request.user.organization,
                actor=request.user,
                request=request,
                **data,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(StockReservationSerializer(reservation).data, status=status.HTTP_201_CREATED)


@extend_schema(request=None, responses={200: StockReservationSerializer})
class ReservationActionView(APIView):
    permission_classes = [IsAuthenticated]
    action = None

    def post(self, request, reservation_id):
        company_ids = authorized_company_ids(request.user, "inventory.stock.reserve")
        try:
            reservation = StockReservation.objects.select_related(
                "company", "warehouse", "warehouse__establishment", "location", "product", "product_variant", "unit", "lot"
            ).get(
                id=reservation_id,
                organization_id=request.user.organization_id,
                company_id__in=company_ids,
            )
        except StockReservation.DoesNotExist as exc:
            from rest_framework.exceptions import NotFound
            raise NotFound() from exc
        if not has_permission(
            request.user,
            "inventory.stock.reserve",
            company=reservation.company,
            establishment=reservation.warehouse.establishment,
        ):
            raise PermissionDenied("You cannot update this reservation.")
        try:
            if self.action == "release":
                reservation = release_reservation(reservation=reservation, actor=request.user, request=request)
            elif self.action == "start-production":
                reservation = start_reservation_production(reservation=reservation, actor=request.user, request=request)
            elif self.action == "consume":
                reservation = consume_reservation(reservation=reservation, actor=request.user, request=request)
            else:
                raise ValidationError("Unsupported reservation action.")
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(StockReservationSerializer(reservation).data)


class ReservationReleaseView(ReservationActionView):
    action = "release"


class ReservationStartProductionView(ReservationActionView):
    action = "start-production"


class ReservationConsumeView(ReservationActionView):
    action = "consume"
