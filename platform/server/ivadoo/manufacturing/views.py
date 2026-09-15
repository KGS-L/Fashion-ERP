from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ivadoo.audit.services import record_audit_event
from ivadoo.authorization.services import authorized_company_ids, has_permission

from .models import BillOfMaterials, ManufacturingOrder
from .serializers import (
    BOMActionSerializer,
    BillOfMaterialsSerializer,
    ManufacturingOrderActionSerializer,
    ManufacturingOrderSerializer,
    MaterialReservationRequestSerializer,
    MaterialReservationResultSerializer,
)
from .services import (
    activate_bom,
    archive_bom,
    bom_snapshot,
    reserve_manufacturing_materials,
    transition_manufacturing_order,
)


def _raise_service_validation(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def scoped_boms(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return BillOfMaterials.objects.none()
    return (
        BillOfMaterials.objects.filter(
            organization_id=user.organization_id,
            company_id__in=company_ids,
        )
        .select_related(
            "company",
            "fashion_model",
            "model_variant",
            "output_product",
            "output_product_variant",
            "created_by",
        )
        .prefetch_related("lines", "lines__product", "lines__product_variant", "lines__unit")
    )


def scoped_orders(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return ManufacturingOrder.objects.none()
    return (
        ManufacturingOrder.objects.filter(
            organization_id=user.organization_id,
            company_id__in=company_ids,
        )
        .select_related(
            "company",
            "warehouse",
            "bom",
            "order",
            "order_line",
            "created_by",
        )
        .prefetch_related(
            "material_requirements",
            "material_requirements__product",
            "material_requirements__product_variant",
            "material_requirements__unit",
        )
    )


class BillOfMaterialsListCreateView(generics.ListCreateAPIView):
    queryset = BillOfMaterials.objects.none()
    serializer_class = BillOfMaterialsSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "fashion_model_id", "model_variant_id", "status", "version")
    search_fields = ("code", "fashion_model__name")
    ordering_fields = ("code", "version", "created_at", "updated_at")
    ordering = ("code", "-version")

    def get_queryset(self):
        return scoped_boms(self.request.user, "manufacturing.bom.view")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        if not has_permission(self.request.user, "manufacturing.bom.manage", company=company):
            raise PermissionDenied("You cannot manage BOMs in this company.")
        with transaction.atomic():
            bom = serializer.save(
                organization=self.request.user.organization,
                created_by=self.request.user,
            )
            record_audit_event(
                organization=bom.organization,
                actor=self.request.user,
                action="manufacturing.bom.create",
                object_instance=bom,
                after=bom_snapshot(bom),
                company_id=bom.company_id,
                request=self.request,
            )


class BillOfMaterialsDetailView(generics.RetrieveUpdateAPIView):
    queryset = BillOfMaterials.objects.none()
    serializer_class = BillOfMaterialsSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "bom_id"

    def get_queryset(self):
        permission = "manufacturing.bom.view" if self.request.method == "GET" else "manufacturing.bom.manage"
        return scoped_boms(self.request.user, permission)

    def perform_update(self, serializer):
        company = serializer.validated_data.get("company", serializer.instance.company)
        if not has_permission(self.request.user, "manufacturing.bom.manage", company=company):
            raise PermissionDenied("You cannot manage BOMs in this company.")
        before = bom_snapshot(serializer.instance)
        with transaction.atomic():
            bom = serializer.save()
            record_audit_event(
                organization=bom.organization,
                actor=self.request.user,
                action="manufacturing.bom.update",
                object_instance=bom,
                before=before,
                after=bom_snapshot(bom),
                company_id=bom.company_id,
                request=self.request,
            )


class BillOfMaterialsActionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=BOMActionSerializer, responses=BillOfMaterialsSerializer)
    def post(self, request, bom_id):
        serializer = BOMActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            bom = scoped_boms(request.user, "manufacturing.bom.manage").get(id=bom_id)
        except BillOfMaterials.DoesNotExist as exc:
            raise NotFound() from exc
        if not has_permission(request.user, "manufacturing.bom.manage", company=bom.company):
            raise PermissionDenied("You cannot manage this BOM.")
        try:
            if serializer.validated_data["action"] == "activate":
                bom = activate_bom(bom=bom, actor=request.user, request=request)
            else:
                bom = archive_bom(bom=bom, actor=request.user, request=request)
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(BillOfMaterialsSerializer(bom, context={"request": request}).data)


class ManufacturingOrderListCreateView(generics.ListCreateAPIView):
    queryset = ManufacturingOrder.objects.none()
    serializer_class = ManufacturingOrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "warehouse_id", "bom_id", "order_id", "status")
    search_fields = ("number", "order__number", "bom__code")
    ordering_fields = ("number", "created_at", "updated_at", "planned_start", "planned_end")
    ordering = ("-created_at",)

    def get_queryset(self):
        return scoped_orders(self.request.user, "manufacturing.order.view")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        warehouse = serializer.validated_data["warehouse"]
        if not has_permission(
            self.request.user,
            "manufacturing.order.manage",
            company=company,
            establishment=warehouse.establishment,
        ):
            raise PermissionDenied("You cannot create manufacturing orders in this scope.")
        serializer.save()


class ManufacturingOrderDetailView(generics.RetrieveAPIView):
    queryset = ManufacturingOrder.objects.none()
    serializer_class = ManufacturingOrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "manufacturing_order_id"

    def get_queryset(self):
        return scoped_orders(self.request.user, "manufacturing.order.view")


class ManufacturingOrderActionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ManufacturingOrderActionSerializer,
        responses=ManufacturingOrderSerializer,
    )
    def post(self, request, manufacturing_order_id):
        serializer = ManufacturingOrderActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            manufacturing_order = scoped_orders(
                request.user, "manufacturing.order.transition"
            ).get(id=manufacturing_order_id)
        except ManufacturingOrder.DoesNotExist as exc:
            raise NotFound() from exc
        if not has_permission(
            request.user,
            "manufacturing.order.transition",
            company=manufacturing_order.company,
            establishment=manufacturing_order.warehouse.establishment,
        ):
            raise PermissionDenied("You cannot transition this manufacturing order.")
        try:
            manufacturing_order = transition_manufacturing_order(
                manufacturing_order=manufacturing_order,
                action=serializer.validated_data["action"],
                actor=request.user,
                reason=serializer.validated_data.get("reason", ""),
                produced_quantity=serializer.validated_data.get("produced_quantity"),
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(
            ManufacturingOrderSerializer(
                manufacturing_order,
                context={"request": request},
            ).data
        )


class ManufacturingMaterialReservationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=MaterialReservationRequestSerializer,
        responses=MaterialReservationResultSerializer,
    )
    def post(self, request, manufacturing_order_id):
        serializer = MaterialReservationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            manufacturing_order = scoped_orders(
                request.user, "manufacturing.material.reserve"
            ).get(id=manufacturing_order_id)
        except ManufacturingOrder.DoesNotExist as exc:
            raise NotFound() from exc
        if not has_permission(
            request.user,
            "manufacturing.material.reserve",
            company=manufacturing_order.company,
            establishment=manufacturing_order.warehouse.establishment,
        ) or not has_permission(
            request.user,
            "inventory.stock.manage",
            company=manufacturing_order.company,
            establishment=manufacturing_order.warehouse.establishment,
        ):
            raise PermissionDenied("You cannot reserve manufacturing materials in this scope.")
        try:
            reservations = reserve_manufacturing_materials(
                manufacturing_order=manufacturing_order,
                allocations=serializer.validated_data["allocations"],
                actor=request.user,
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(
            MaterialReservationResultSerializer(
                {"reservation_ids": [item.id for item in reservations]}
            ).data
        )
