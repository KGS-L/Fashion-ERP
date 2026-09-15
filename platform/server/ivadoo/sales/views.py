from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ivadoo.audit.services import record_audit_event
from ivadoo.authorization.services import authorized_company_ids, has_permission

from .models import Order, Quotation
from .serializers import OrderSerializer, QuotationSerializer


def scoped(model, user, permission):
    return model.objects.filter(
        organization_id=user.organization_id,
        company_id__in=authorized_company_ids(user, permission),
    )


class QuotationListCreateView(generics.ListCreateAPIView):
    queryset = Quotation.objects.none()
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "customer_id", "status")
    search_fields = ("number", "customer__display_name")

    def get_queryset(self):
        return scoped(
            Quotation,
            self.request.user,
            "fashion.sale.view",
        ).prefetch_related("lines")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        customer = serializer.validated_data["customer"]
        if customer.company_id != company.id or not has_permission(
            self.request.user,
            "fashion.sale.manage",
            company=company,
        ):
            raise PermissionDenied()
        quotation = serializer.save(organization=self.request.user.organization)
        record_audit_event(
            organization=self.request.user.organization,
            actor=self.request.user,
            action="fashion.quotation.create",
            object_instance=quotation,
            request=self.request,
        )


class OrderListCreateView(generics.ListCreateAPIView):
    queryset = Order.objects.none()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "customer_id", "status")
    search_fields = ("number", "customer__display_name")

    def get_queryset(self):
        return scoped(
            Order,
            self.request.user,
            "fashion.sale.view",
        ).prefetch_related("lines")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        customer = serializer.validated_data["customer"]
        if customer.company_id != company.id or not has_permission(
            self.request.user,
            "fashion.sale.manage",
            company=company,
        ):
            raise PermissionDenied()
        serializer.save(organization=self.request.user.organization)


class QuotationActionView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QuotationSerializer

    def post(self, request, quotation_id, action):
        if action not in {"send", "accept", "reject", "expire"}:
            return Response(status=status.HTTP_404_NOT_FOUND)

        quotation = get_object_or_404(
            scoped(Quotation, request.user, "fashion.sale.manage"),
            id=quotation_id,
        )
        allowed = {
            "send": (Quotation.Status.DRAFT, Quotation.Status.SENT),
            "accept": (Quotation.Status.SENT, Quotation.Status.ACCEPTED),
            "reject": (Quotation.Status.SENT, Quotation.Status.REJECTED),
            "expire": (Quotation.Status.SENT, Quotation.Status.EXPIRED),
        }
        source, destination = allowed[action]
        if quotation.status != source:
            raise ValidationError(
                {"status": f"Cannot {action} quotation from {quotation.status}."}
            )

        quotation.status = destination
        quotation.save(update_fields=["status", "updated_at"])
        record_audit_event(
            organization=request.user.organization,
            actor=request.user,
            action=f"fashion.quotation.{action}",
            object_instance=quotation,
            request=request,
        )
        return Response(QuotationSerializer(quotation).data)


class OrderActionView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def post(self, request, order_id, action):
        with transaction.atomic():
            order = get_object_or_404(
                scoped(Order, request.user, "fashion.sale.manage")
                .select_for_update()
                .prefetch_related("lines__measurement_set__values__definition"),
                id=order_id,
            )
            if action == "confirm":
                if order.status != Order.Status.DRAFT:
                    raise ValidationError(
                        {"status": "Only draft orders can be confirmed."}
                    )
                for line in order.lines.all():
                    measurement_set = line.measurement_set
                    if measurement_set:
                        line.measurement_snapshot = {
                            "measurement_set_id": str(measurement_set.id),
                            "version": measurement_set.version,
                            "measured_at": measurement_set.measured_at.isoformat(),
                            "values": [
                                {
                                    "definition_id": str(value.definition_id),
                                    "code": value.definition.code,
                                    "value": str(value.value),
                                    "tolerance": (
                                        str(value.tolerance)
                                        if value.tolerance is not None
                                        else None
                                    ),
                                    "note": value.note,
                                }
                                for value in measurement_set.values.all()
                            ],
                        }
                        line.measurement_source_version = measurement_set.version
                        line.save(
                            update_fields=[
                                "measurement_snapshot",
                                "measurement_source_version",
                            ]
                        )
                order.status = Order.Status.CONFIRMED
                order.confirmed_at = timezone.now()
                order.save(update_fields=["status", "confirmed_at", "updated_at"])
            elif action == "cancel":
                if order.status == Order.Status.CANCELLED:
                    raise ValidationError({"status": "Order is already cancelled."})
                order.status = Order.Status.CANCELLED
                order.cancelled_at = timezone.now()
                order.save(update_fields=["status", "cancelled_at", "updated_at"])
            else:
                return Response(status=status.HTTP_404_NOT_FOUND)

            record_audit_event(
                organization=request.user.organization,
                actor=request.user,
                action=f"fashion.order.{action}",
                object_instance=order,
                request=request,
            )
            return Response(OrderSerializer(order).data)
