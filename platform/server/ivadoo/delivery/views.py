from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ivadoo.authorization.services import authorized_company_ids, has_permission

from .models import Delivery
from .serializers import DeliveryActionSerializer, DeliverySerializer
from .services import transition_delivery


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
