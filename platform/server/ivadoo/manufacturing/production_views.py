from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ivadoo.authorization.services import has_permission

from .models import ManufacturingOrder
from .production_models import (
    ManufacturingMaterialConsumption,
    ManufacturingMaterialRemnant,
)
from .production_serializers import (
    CompleteProductionRequestSerializer,
    ManufacturingMaterialConsumptionSerializer,
    ManufacturingMaterialRemnantSerializer,
    ManufacturingOutputReceiptSerializer,
    MaterialConsumptionRequestSerializer,
    MaterialVarianceRowSerializer,
    ReusableRemnantRequestSerializer,
)
from .production_services import (
    complete_manufacturing_order,
    consume_manufacturing_materials,
    material_variance,
    record_reusable_remnant,
)
from .views import scoped_orders


def _raise_service_validation(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def _scoped_order(request, manufacturing_order_id, permission_code):
    try:
        return scoped_orders(request.user, permission_code).get(id=manufacturing_order_id)
    except ManufacturingOrder.DoesNotExist as exc:
        raise NotFound() from exc


class ManufacturingMaterialConsumptionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ManufacturingMaterialConsumptionSerializer(many=True))
    def get(self, request, manufacturing_order_id):
        manufacturing_order = _scoped_order(
            request, manufacturing_order_id, "manufacturing.order.view"
        )
        rows = ManufacturingMaterialConsumption.objects.filter(
            manufacturing_order=manufacturing_order
        ).select_related("stock_movement")
        return Response(ManufacturingMaterialConsumptionSerializer(rows, many=True).data)

    @extend_schema(
        request=MaterialConsumptionRequestSerializer,
        responses=ManufacturingMaterialConsumptionSerializer(many=True),
    )
    def post(self, request, manufacturing_order_id):
        manufacturing_order = _scoped_order(
            request, manufacturing_order_id, "manufacturing.material.consume"
        )
        if not has_permission(
            request.user,
            "manufacturing.material.consume",
            company=manufacturing_order.company,
            establishment=manufacturing_order.warehouse.establishment,
        ):
            raise PermissionDenied("You cannot consume manufacturing materials in this scope.")
        serializer = MaterialConsumptionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if any(
            not allocation.get("reservation")
            for allocation in serializer.validated_data["allocations"]
        ) and not has_permission(
            request.user,
            "manufacturing.material.consume_supplemental",
            company=manufacturing_order.company,
            establishment=manufacturing_order.warehouse.establishment,
        ):
            raise PermissionDenied("Supplemental material consumption requires an additional permission.")
        try:
            consumptions = consume_manufacturing_materials(
                manufacturing_order=manufacturing_order,
                allocations=serializer.validated_data["allocations"],
                actor=request.user,
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(
            ManufacturingMaterialConsumptionSerializer(consumptions, many=True).data,
            status=status.HTTP_200_OK,
        )


class ManufacturingMaterialRemnantView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ManufacturingMaterialRemnantSerializer(many=True))
    def get(self, request, manufacturing_order_id):
        manufacturing_order = _scoped_order(
            request, manufacturing_order_id, "manufacturing.order.view"
        )
        rows = ManufacturingMaterialRemnant.objects.filter(
            manufacturing_order=manufacturing_order
        ).select_related("stock_lot", "stock_movement")
        return Response(ManufacturingMaterialRemnantSerializer(rows, many=True).data)

    @extend_schema(
        request=ReusableRemnantRequestSerializer,
        responses=ManufacturingMaterialRemnantSerializer,
    )
    def post(self, request, manufacturing_order_id):
        manufacturing_order = _scoped_order(
            request, manufacturing_order_id, "manufacturing.material.remnant"
        )
        if not has_permission(
            request.user,
            "manufacturing.material.remnant",
            company=manufacturing_order.company,
            establishment=manufacturing_order.warehouse.establishment,
        ):
            raise PermissionDenied("You cannot record reusable remnants in this scope.")
        serializer = ReusableRemnantRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            remnant = record_reusable_remnant(
                manufacturing_order=manufacturing_order,
                requirement_id=serializer.validated_data["requirement_id"],
                location=serializer.validated_data["location"],
                quantity=serializer.validated_data["quantity"],
                code=serializer.validated_data["code"],
                idempotency_key=serializer.validated_data["idempotency_key"],
                reason=serializer.validated_data.get("reason", ""),
                actor=request.user,
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(
            ManufacturingMaterialRemnantSerializer(remnant).data,
            status=status.HTTP_201_CREATED,
        )


class ManufacturingMaterialVarianceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MaterialVarianceRowSerializer(many=True))
    def get(self, request, manufacturing_order_id):
        manufacturing_order = _scoped_order(
            request, manufacturing_order_id, "manufacturing.order.view"
        )
        return Response(
            MaterialVarianceRowSerializer(
                material_variance(manufacturing_order), many=True
            ).data
        )


class ManufacturingOrderCompletionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=CompleteProductionRequestSerializer,
        responses=ManufacturingOutputReceiptSerializer,
    )
    def post(self, request, manufacturing_order_id):
        manufacturing_order = _scoped_order(
            request, manufacturing_order_id, "manufacturing.order.complete"
        )
        if not has_permission(
            request.user,
            "manufacturing.order.complete",
            company=manufacturing_order.company,
            establishment=manufacturing_order.warehouse.establishment,
        ) or not has_permission(
            request.user,
            "inventory.stock.manage",
            company=manufacturing_order.company,
            establishment=manufacturing_order.warehouse.establishment,
        ):
            raise PermissionDenied("You cannot complete production into stock in this scope.")
        serializer = CompleteProductionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            receipt = complete_manufacturing_order(
                manufacturing_order=manufacturing_order,
                produced_quantity=serializer.validated_data["produced_quantity"],
                destination_location=serializer.validated_data["destination_location"],
                actor=request.user,
                reason=serializer.validated_data.get("reason", ""),
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(ManufacturingOutputReceiptSerializer(receipt).data)
