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

from .fitting_serializers import (
    AlterationActionSerializer,
    AlterationRequestSerializer,
    CustomerValidationSerializer,
    DeliveryReadinessSerializer,
    FittingActionSerializer,
    FittingSessionSerializer,
)
from .fitting_services import (
    fitting_snapshot,
    order_delivery_readiness,
    record_customer_validation,
    transition_alteration,
    transition_fitting,
)
from .models import AlterationRequest, CustomerValidation, FittingSession, Order


def _raise_service_validation(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def scoped_fittings(user, permission_code):
    companies = authorized_company_ids(user, permission_code)
    if not companies:
        return FittingSession.objects.none()
    return FittingSession.objects.filter(organization_id=user.organization_id, company_id__in=companies).select_related("order", "company", "created_by")


def scoped_alterations(user, permission_code):
    companies = authorized_company_ids(user, permission_code)
    if not companies:
        return AlterationRequest.objects.none()
    return AlterationRequest.objects.filter(organization_id=user.organization_id, company_id__in=companies).select_related(
        "order", "fitting", "order_line", "quality_defect", "manufacturing_order", "manufacturing_operation"
    )


def scoped_validations(user, permission_code):
    companies = authorized_company_ids(user, permission_code)
    if not companies:
        return CustomerValidation.objects.none()
    return CustomerValidation.objects.filter(organization_id=user.organization_id, company_id__in=companies).select_related("order", "fitting", "recorded_by")


class FittingSessionListCreateView(generics.ListCreateAPIView):
    queryset = FittingSession.objects.none()
    serializer_class = FittingSessionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "order_id", "status", "result", "requires_customer_validation")
    ordering_fields = ("scheduled_at", "performed_at", "created_at")
    ordering = ("-scheduled_at",)

    def get_queryset(self):
        return scoped_fittings(self.request.user, "fashion.fitting.view")

    def perform_create(self, serializer):
        order = serializer.validated_data["order"]
        if not has_permission(self.request.user, "fashion.fitting.manage", company=order.company):
            raise PermissionDenied("You cannot manage fittings in this scope.")
        with transaction.atomic():
            fitting = serializer.save(
                organization=self.request.user.organization,
                company=order.company,
                created_by=self.request.user,
            )
            fitting.full_clean()
            fitting.save()
            record_audit_event(
                organization=fitting.organization,
                actor=self.request.user,
                action="fashion.fitting.create",
                object_instance=fitting,
                after=fitting_snapshot(fitting),
                company_id=fitting.company_id,
                request=self.request,
            )


class FittingSessionDetailView(generics.RetrieveAPIView):
    queryset = FittingSession.objects.none()
    serializer_class = FittingSessionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "fitting_id"

    def get_queryset(self):
        return scoped_fittings(self.request.user, "fashion.fitting.view")


class FittingActionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=FittingActionSerializer, responses=FittingSessionSerializer)
    def post(self, request, fitting_id, action):
        serializer = FittingActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            fitting = scoped_fittings(request.user, "fashion.fitting.manage").get(id=fitting_id)
        except FittingSession.DoesNotExist as exc:
            raise NotFound() from exc
        if not has_permission(request.user, "fashion.fitting.manage", company=fitting.company):
            raise PermissionDenied("You cannot transition this fitting.")
        try:
            fitting = transition_fitting(
                fitting=fitting,
                action=action,
                actor=request.user,
                result=serializer.validated_data.get("result"),
                notes=serializer.validated_data.get("notes"),
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(FittingSessionSerializer(fitting, context={"request": request}).data)


class AlterationListCreateView(generics.ListCreateAPIView):
    queryset = AlterationRequest.objects.none()
    serializer_class = AlterationRequestSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "order_id", "fitting_id", "status", "priority", "manufacturing_order_id")
    ordering_fields = ("created_at", "started_at", "completed_at")
    ordering = ("-created_at",)

    def get_queryset(self):
        return scoped_alterations(self.request.user, "fashion.fitting.view")

    def perform_create(self, serializer):
        fitting = serializer.validated_data["fitting"]
        if not has_permission(self.request.user, "fashion.alteration.manage", company=fitting.company):
            raise PermissionDenied("You cannot manage alterations in this scope.")
        with transaction.atomic():
            alteration = serializer.save(
                organization=self.request.user.organization,
                company=fitting.company,
                order=fitting.order,
                created_by=self.request.user,
            )
            alteration.full_clean()
            alteration.save()
            record_audit_event(
                organization=alteration.organization,
                actor=self.request.user,
                action="fashion.alteration.create",
                object_instance=alteration,
                company_id=alteration.company_id,
                request=self.request,
            )


class AlterationActionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AlterationActionSerializer, responses=AlterationRequestSerializer)
    def post(self, request, alteration_id, action):
        serializer = AlterationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            alteration = scoped_alterations(request.user, "fashion.alteration.manage").get(id=alteration_id)
        except AlterationRequest.DoesNotExist as exc:
            raise NotFound() from exc
        if not has_permission(request.user, "fashion.alteration.manage", company=alteration.company):
            raise PermissionDenied("You cannot transition this alteration.")
        reopen_operation = serializer.validated_data.get("reopen_operation", False)
        allow_operation_rework = has_permission(request.user, "manufacturing.operation.transition", company=alteration.company)
        try:
            alteration = transition_alteration(
                alteration=alteration,
                action=action,
                actor=request.user,
                reopen_operation=reopen_operation,
                allow_operation_rework=allow_operation_rework,
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(AlterationRequestSerializer(alteration, context={"request": request}).data)


class CustomerValidationListCreateView(generics.ListCreateAPIView):
    queryset = CustomerValidation.objects.none()
    serializer_class = CustomerValidationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "order_id", "decision")
    ordering = ("-validated_at",)

    def get_queryset(self):
        return scoped_validations(self.request.user, "fashion.fitting.view")

    def perform_create(self, serializer):
        fitting = serializer.validated_data["fitting"]
        if not has_permission(self.request.user, "fashion.customer_validation.manage", company=fitting.company):
            raise PermissionDenied("You cannot record customer validation in this scope.")
        try:
            record_customer_validation(
                fitting=fitting,
                decision=serializer.validated_data["decision"],
                actor=self.request.user,
                customer_name=serializer.validated_data.get("customer_name", ""),
                notes=serializer.validated_data.get("notes", ""),
                evidence_reference=serializer.validated_data.get("evidence_reference", ""),
                request=self.request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fitting = serializer.validated_data["fitting"]
        if not has_permission(request.user, "fashion.customer_validation.manage", company=fitting.company):
            raise PermissionDenied("You cannot record customer validation in this scope.")
        try:
            validation = record_customer_validation(
                fitting=fitting,
                decision=serializer.validated_data["decision"],
                actor=request.user,
                customer_name=serializer.validated_data.get("customer_name", ""),
                notes=serializer.validated_data.get("notes", ""),
                evidence_reference=serializer.validated_data.get("evidence_reference", ""),
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        output = CustomerValidationSerializer(validation, context={"request": request})
        return Response(output.data, status=201)


class OrderDeliveryReadinessView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=DeliveryReadinessSerializer)
    def get(self, request, order_id):
        companies = authorized_company_ids(request.user, "fashion.sale.view")
        try:
            order = Order.objects.filter(organization_id=request.user.organization_id, company_id__in=companies).get(id=order_id)
        except Order.DoesNotExist as exc:
            raise NotFound() from exc
        return Response(DeliveryReadinessSerializer(order_delivery_readiness(order)).data)
