from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ivadoo.authorization.services import authorized_company_ids, has_permission
from ivadoo.sales.models import Order

from .models import Delivery, DeliveryReturn
from .serializers import (
    DeliveryActionSerializer,
    DeliveryBalanceSerializer,
    DeliveryReturnSerializer,
    DeliverySerializer,
)
from .services import order_delivery_balance, transition_delivery


def _raise_service_validation(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def scoped_deliveries(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return Delivery.objects.none()
    return (
        Delivery.objects.filter(organization_id=user.organization_id, company_id__in=company_ids)
        .select_related("order", "company", "created_by")
        .prefetch_related("lines", "packages")
    )


def scoped_returns(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return DeliveryReturn.objects.none()
    return (
        DeliveryReturn.objects.filter(organization_id=user.organization_id, company_id__in=company_ids)
        .select_related("delivery", "company", "created_by")
        .prefetch_related(
            "lines__delivery_line",
            "lines__destination_location",
            "lines__stock_allocations",
        )
    )


class DeliveryListCreateView(generics.ListCreateAPIView):
    queryset = Delivery.objects.none()
    serializer_class = DeliverySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "order_id", "mode", "status")
    ordering_fields = ("created_at", "prepared_at", "completed_at")
    ordering = ("-created_at",)

    def get_queryset(self):
        return scoped_deliveries(self.request.user, "delivery.delivery.view")

    def perform_create(self, serializer):
        order = serializer.validated_data["order"]
        if not has_permission(self.request.user, "delivery.delivery.manage", company=order.company):
            raise PermissionDenied("You cannot create deliveries in this scope.")
        try:
            serializer.save()
        except DjangoValidationError as exc:
            _raise_service_validation(exc)


class DeliveryDetailView(generics.RetrieveAPIView):
    queryset = Delivery.objects.none()
    serializer_class = DeliverySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "delivery_id"

    def get_queryset(self):
        return scoped_deliveries(self.request.user, "delivery.delivery.view")


class DeliveryActionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=DeliveryActionSerializer, responses=DeliverySerializer)
    def post(self, request, delivery_id, action):
        serializer = DeliveryActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            delivery = scoped_deliveries(request.user, "delivery.delivery.transition").get(id=delivery_id)
        except Delivery.DoesNotExist as exc:
            raise NotFound() from exc
        if not has_permission(request.user, "delivery.delivery.transition", company=delivery.company):
            raise PermissionDenied("You cannot transition this delivery.")
        try:
            delivery = transition_delivery(
                delivery=delivery,
                action=action,
                actor=request.user,
                proof=serializer.validated_data.get("proof"),
                failure_reason=serializer.validated_data.get("failure_reason", ""),
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        delivery.refresh_from_db()
        return Response(DeliverySerializer(delivery, context={"request": request}).data)


class DeliveryReturnListCreateView(generics.ListCreateAPIView):
    queryset = DeliveryReturn.objects.none()
    serializer_class = DeliveryReturnSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "delivery_id", "resolution")
    ordering_fields = ("created_at", "number")
    ordering = ("-created_at",)

    def get_queryset(self):
        return scoped_returns(self.request.user, "delivery.return.view")

    def perform_create(self, serializer):
        delivery = serializer.validated_data["delivery"]
        if not has_permission(self.request.user, "delivery.return.manage", company=delivery.company):
            raise PermissionDenied("You cannot record returns in this scope.")
        try:
            serializer.save()
        except DjangoValidationError as exc:
            _raise_service_validation(exc)


class DeliveryReturnDetailView(generics.RetrieveAPIView):
    queryset = DeliveryReturn.objects.none()
    serializer_class = DeliveryReturnSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "return_id"

    def get_queryset(self):
        return scoped_returns(self.request.user, "delivery.return.view")


class DeliveryBalanceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=DeliveryBalanceSerializer)
    def get(self, request, order_id):
        company_ids = authorized_company_ids(request.user, "delivery.delivery.view")
        try:
            order = Order.objects.prefetch_related("lines").get(
                id=order_id,
                organization_id=request.user.organization_id,
                company_id__in=company_ids,
            )
        except Order.DoesNotExist as exc:
            raise NotFound() from exc
        return Response(DeliveryBalanceSerializer(order_delivery_balance(order)).data)
