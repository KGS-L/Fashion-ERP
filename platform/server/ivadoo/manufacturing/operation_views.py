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

from .models import ManufacturingOperation, ManufacturingOrder, WorkCenter
from .operation_serializers import (
    ManufacturingOperationActionSerializer,
    ManufacturingOperationSerializer,
    WorkCenterSerializer,
)
from .operation_services import operation_snapshot, transition_operation


def _raise_service_validation(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def work_center_snapshot(work_center):
    return {
        "company_id": str(work_center.company_id),
        "establishment_id": str(work_center.establishment_id) if work_center.establishment_id else None,
        "code": work_center.code,
        "name": work_center.name,
        "is_active": work_center.is_active,
    }


def scoped_work_centers(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return WorkCenter.objects.none()
    return WorkCenter.objects.filter(
        organization_id=user.organization_id,
        company_id__in=company_ids,
    ).select_related("company", "establishment")


def scoped_operations(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return ManufacturingOperation.objects.none()
    return (
        ManufacturingOperation.objects.filter(
            organization_id=user.organization_id,
            company_id__in=company_ids,
        )
        .select_related(
            "company",
            "manufacturing_order",
            "manufacturing_order__warehouse",
            "work_center",
            "created_by",
        )
        .prefetch_related("history", "history__actor")
    )


def scoped_manufacturing_orders(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return ManufacturingOrder.objects.none()
    return ManufacturingOrder.objects.filter(
        organization_id=user.organization_id,
        company_id__in=company_ids,
    ).select_related("company", "warehouse", "warehouse__establishment")


class WorkCenterListCreateView(generics.ListCreateAPIView):
    queryset = WorkCenter.objects.none()
    serializer_class = WorkCenterSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "establishment_id", "is_active")
    search_fields = ("code", "name")
    ordering_fields = ("code", "name", "created_at", "updated_at")
    ordering = ("company__name", "code")

    def get_queryset(self):
        return scoped_work_centers(self.request.user, "manufacturing.work_center.view")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        establishment = serializer.validated_data.get("establishment")
        if not has_permission(
            self.request.user,
            "manufacturing.work_center.manage",
            company=company,
            establishment=establishment,
        ):
            raise PermissionDenied("You cannot manage work centers in this scope.")
        with transaction.atomic():
            work_center = serializer.save(organization=self.request.user.organization)
            record_audit_event(
                organization=work_center.organization,
                actor=self.request.user,
                action="manufacturing.work_center.create",
                object_instance=work_center,
                after=work_center_snapshot(work_center),
                company_id=work_center.company_id,
                request=self.request,
            )


class WorkCenterDetailView(generics.RetrieveUpdateAPIView):
    queryset = WorkCenter.objects.none()
    serializer_class = WorkCenterSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "work_center_id"

    def get_queryset(self):
        permission = (
            "manufacturing.work_center.view"
            if self.request.method == "GET"
            else "manufacturing.work_center.manage"
        )
        return scoped_work_centers(self.request.user, permission)

    def perform_update(self, serializer):
        company = serializer.instance.company
        establishment = serializer.validated_data.get(
            "establishment", serializer.instance.establishment
        )
        if not has_permission(
            self.request.user,
            "manufacturing.work_center.manage",
            company=company,
            establishment=establishment,
        ):
            raise PermissionDenied("You cannot manage this work center.")
        before = work_center_snapshot(serializer.instance)
        with transaction.atomic():
            work_center = serializer.save()
            record_audit_event(
                organization=work_center.organization,
                actor=self.request.user,
                action="manufacturing.work_center.update",
                object_instance=work_center,
                before=before,
                after=work_center_snapshot(work_center),
                company_id=work_center.company_id,
                request=self.request,
            )


class ManufacturingOperationListCreateView(generics.ListCreateAPIView):
    queryset = ManufacturingOperation.objects.none()
    serializer_class = ManufacturingOperationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("operation_type", "status", "work_center_id")
    search_fields = ("name", "work_center__name", "work_center__code")
    ordering_fields = ("position", "created_at", "updated_at")
    ordering = ("position",)

    def _manufacturing_order(self):
        permission = (
            "manufacturing.operation.view"
            if self.request.method == "GET"
            else "manufacturing.operation.manage"
        )
        try:
            return scoped_manufacturing_orders(self.request.user, permission).get(
                id=self.kwargs["manufacturing_order_id"]
            )
        except ManufacturingOrder.DoesNotExist as exc:
            raise NotFound() from exc

    def get_queryset(self):
        manufacturing_order = self._manufacturing_order()
        return scoped_operations(
            self.request.user, "manufacturing.operation.view"
        ).filter(manufacturing_order=manufacturing_order)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["manufacturing_order"] = self._manufacturing_order()
        return context

    def perform_create(self, serializer):
        manufacturing_order = self._manufacturing_order()
        if not has_permission(
            self.request.user,
            "manufacturing.operation.manage",
            company=manufacturing_order.company,
            establishment=manufacturing_order.warehouse.establishment,
        ):
            raise PermissionDenied("You cannot plan manufacturing operations in this scope.")
        with transaction.atomic():
            operation = serializer.save()
            record_audit_event(
                organization=operation.organization,
                actor=self.request.user,
                action="manufacturing.operation.create",
                object_instance=operation,
                after=operation_snapshot(operation),
                company_id=operation.company_id,
                request=self.request,
            )


class ManufacturingOperationDetailView(generics.RetrieveAPIView):
    queryset = ManufacturingOperation.objects.none()
    serializer_class = ManufacturingOperationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "operation_id"

    def get_queryset(self):
        return scoped_operations(self.request.user, "manufacturing.operation.view")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        operation = self.get_object()
        context["manufacturing_order"] = operation.manufacturing_order
        return context


class ManufacturingOperationActionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ManufacturingOperationActionSerializer,
        responses=ManufacturingOperationSerializer,
    )
    def post(self, request, operation_id):
        serializer = ManufacturingOperationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            operation = scoped_operations(
                request.user, "manufacturing.operation.transition"
            ).get(id=operation_id)
        except ManufacturingOperation.DoesNotExist as exc:
            raise NotFound() from exc
        establishment = operation.manufacturing_order.warehouse.establishment
        if not has_permission(
            request.user,
            "manufacturing.operation.transition",
            company=operation.company,
            establishment=establishment,
        ):
            raise PermissionDenied("You cannot transition this manufacturing operation.")
        override_sequence = serializer.validated_data.get("override_sequence", False)
        allow_override = has_permission(
            request.user,
            "manufacturing.operation.override_sequence",
            company=operation.company,
            establishment=establishment,
        )
        if override_sequence and not allow_override:
            raise PermissionDenied("You cannot override the manufacturing operation sequence.")
        try:
            operation = transition_operation(
                operation=operation,
                action=serializer.validated_data["action"],
                actor=request.user,
                reason=serializer.validated_data.get("reason", ""),
                processed_quantity=serializer.validated_data.get("processed_quantity"),
                actual_minutes=serializer.validated_data.get("actual_minutes"),
                override_sequence=override_sequence,
                allow_sequence_override=allow_override,
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(
            ManufacturingOperationSerializer(
                operation,
                context={
                    "request": request,
                    "manufacturing_order": operation.manufacturing_order,
                },
            ).data
        )
