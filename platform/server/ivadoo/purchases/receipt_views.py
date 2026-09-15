from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ivadoo.audit.services import record_audit_event
from ivadoo.authorization.services import authorized_company_ids, has_permission

from .models import PurchaseReceipt, Supplier, SupplierPurchaseHistory
from .receipt_serializers import (
    PurchaseReceiptSerializer,
    ReceiptActionSerializer,
    SupplierPerformanceSerializer,
)
from .receipt_services import cancel_receipt, control_receipt, post_receipt


def _raise_service_validation(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def scoped_receipts(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return PurchaseReceipt.objects.none()
    return (
        PurchaseReceipt.objects.filter(
            organization_id=user.organization_id,
            company_id__in=company_ids,
        )
        .select_related(
            "company",
            "purchase_order",
            "purchase_order__supplier",
            "warehouse",
            "created_by",
            "controlled_by",
            "posted_by",
        )
        .prefetch_related(
            "lines",
            "lines__purchase_order_line",
            "lines__location",
            "lines__stock_movement",
        )
    )


class PurchaseReceiptListCreateView(generics.ListCreateAPIView):
    queryset = PurchaseReceipt.objects.none()
    serializer_class = PurchaseReceiptSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = (
        "company_id",
        "purchase_order_id",
        "warehouse_id",
        "status",
    )
    search_fields = (
        "number",
        "supplier_delivery_reference",
        "purchase_order__number",
        "purchase_order__supplier__name",
    )
    ordering_fields = ("number", "received_at", "created_at", "updated_at")
    ordering = ("-received_at",)

    def get_queryset(self):
        return scoped_receipts(self.request.user, "purchase.receipt.view")

    def perform_create(self, serializer):
        purchase_order = serializer.validated_data["purchase_order"]
        warehouse = serializer.validated_data["warehouse"]
        if not has_permission(
            self.request.user,
            "purchase.receipt.manage",
            company=purchase_order.company,
            establishment=warehouse.establishment,
        ):
            raise PermissionDenied("You cannot create receipts in this stock scope.")
        with transaction.atomic():
            receipt = serializer.save(created_by=self.request.user)
            record_audit_event(
                organization=receipt.organization,
                actor=self.request.user,
                action="purchase.receipt.create",
                object_instance=receipt,
                after={
                    "number": receipt.number,
                    "purchase_order_id": str(receipt.purchase_order_id),
                    "warehouse_id": str(receipt.warehouse_id),
                    "status": receipt.status,
                },
                company_id=receipt.company_id,
                request=self.request,
            )


class PurchaseReceiptDetailView(generics.RetrieveAPIView):
    queryset = PurchaseReceipt.objects.none()
    serializer_class = PurchaseReceiptSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "receipt_id"

    def get_queryset(self):
        return scoped_receipts(self.request.user, "purchase.receipt.view")


class PurchaseReceiptActionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ReceiptActionSerializer, responses=PurchaseReceiptSerializer)
    def post(self, request, receipt_id):
        serializer = ReceiptActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        permission = {
            "control": "purchase.receipt.control",
            "post": "purchase.receipt.post",
            "cancel": "purchase.receipt.manage",
        }[action]
        try:
            receipt = scoped_receipts(request.user, permission).get(id=receipt_id)
        except PurchaseReceipt.DoesNotExist as exc:
            raise NotFound() from exc
        if not has_permission(
            request.user,
            permission,
            company=receipt.company,
            establishment=receipt.warehouse.establishment,
        ):
            raise PermissionDenied("You cannot perform this receipt action.")
        try:
            if action == "control":
                receipt = control_receipt(
                    receipt=receipt,
                    decisions=serializer.validated_data["lines"],
                    actor=request.user,
                    reason=serializer.validated_data.get("reason", ""),
                    request=request,
                )
            elif action == "post":
                receipt = post_receipt(
                    receipt=receipt,
                    actor=request.user,
                    reason=serializer.validated_data.get("reason", ""),
                    request=request,
                )
            else:
                receipt = cancel_receipt(
                    receipt=receipt,
                    actor=request.user,
                    reason=serializer.validated_data.get("reason", ""),
                    request=request,
                )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(PurchaseReceiptSerializer(receipt, context={"request": request}).data)


class SupplierPerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=SupplierPerformanceSerializer)
    def get(self, request, supplier_id):
        company_ids = authorized_company_ids(request.user, "purchase.supplier.view")
        try:
            supplier = Supplier.objects.get(
                id=supplier_id,
                organization_id=request.user.organization_id,
                company_id__in=company_ids,
            )
        except Supplier.DoesNotExist as exc:
            raise NotFound() from exc

        rows = list(
            SupplierPurchaseHistory.objects.filter(
                organization_id=request.user.organization_id,
                supplier=supplier,
            ).select_related("receipt_line", "receipt_line__receipt")
        )
        total_received = sum((row.received_quantity for row in rows), Decimal("0"))
        total_accepted = sum((row.accepted_quantity for row in rows), Decimal("0"))
        total_rejected = sum((row.rejected_quantity for row in rows), Decimal("0"))
        acceptance_rate = (
            (total_accepted / total_received * Decimal("100"))
            if total_received
            else Decimal("0")
        ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        timed = [row for row in rows if row.on_time is not None]
        on_time_rate = None
        if timed:
            on_time_rate = (
                Decimal(sum(1 for row in timed if row.on_time))
                / Decimal(len(timed))
                * Decimal("100")
            ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        average_lead = None
        if rows:
            average_lead = (
                Decimal(sum(row.lead_time_days for row in rows)) / Decimal(len(rows))
            ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        receipt_count = len({row.receipt_line.receipt_id for row in rows})
        payload = {
            "supplier_id": supplier.id,
            "receipt_count": receipt_count,
            "line_count": len(rows),
            "total_received": total_received,
            "total_accepted": total_accepted,
            "total_rejected": total_rejected,
            "acceptance_rate": acceptance_rate,
            "on_time_rate": on_time_rate,
            "average_lead_time_days": average_lead,
        }
        return Response(SupplierPerformanceSerializer(payload).data, status=status.HTTP_200_OK)
