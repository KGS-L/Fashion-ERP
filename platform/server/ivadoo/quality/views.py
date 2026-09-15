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

from .models import QualityInspection, QualityRework
from .serializers import (
    QualityInspectionCompleteSerializer,
    QualityInspectionSerializer,
    QualityReworkCompleteSerializer,
    QualityReworkSerializer,
    QualitySummarySerializer,
)
from .services import complete_inspection, complete_rework, inspection_snapshot, quality_summary


def _raise_service_validation(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def scoped_inspections(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return QualityInspection.objects.none()
    return (
        QualityInspection.objects.filter(organization_id=user.organization_id, company_id__in=company_ids)
        .select_related(
            "company", "purchase_receipt_line", "manufacturing_order", "manufacturing_operation",
            "output_receipt", "parent_inspection", "created_by", "completed_by",
        )
        .prefetch_related("criteria", "defects")
    )


def scoped_reworks(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return QualityRework.objects.none()
    return QualityRework.objects.filter(organization_id=user.organization_id, company_id__in=company_ids).select_related("inspection", "manufacturing_operation")


class QualityInspectionListCreateView(generics.ListCreateAPIView):
    queryset = QualityInspection.objects.none()
    serializer_class = QualityInspectionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "inspection_type", "status", "decision", "blocking")
    ordering_fields = ("created_at", "completed_at")
    ordering = ("-created_at",)

    def get_queryset(self):
        return scoped_inspections(self.request.user, "quality.inspection.view")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        if not has_permission(self.request.user, "quality.inspection.manage", company=company):
            raise PermissionDenied("You cannot create quality inspections in this scope.")
        with transaction.atomic():
            inspection = serializer.save(
                organization=self.request.user.organization,
                created_by=self.request.user,
            )
            record_audit_event(
                organization=inspection.organization,
                actor=self.request.user,
                action="quality.inspection.create",
                object_instance=inspection,
                after=inspection_snapshot(inspection),
                company_id=inspection.company_id,
                request=self.request,
            )


class QualityInspectionDetailView(generics.RetrieveAPIView):
    queryset = QualityInspection.objects.none()
    serializer_class = QualityInspectionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "inspection_id"

    def get_queryset(self):
        return scoped_inspections(self.request.user, "quality.inspection.view")


class QualityInspectionCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=QualityInspectionCompleteSerializer, responses=QualityInspectionSerializer)
    def post(self, request, inspection_id):
        serializer = QualityInspectionCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            inspection = scoped_inspections(request.user, "quality.inspection.complete").get(id=inspection_id)
        except QualityInspection.DoesNotExist as exc:
            raise NotFound() from exc
        if not has_permission(request.user, "quality.inspection.complete", company=inspection.company):
            raise PermissionDenied("You cannot complete this quality inspection.")
        try:
            inspection = complete_inspection(
                inspection=inspection,
                decision=serializer.validated_data["decision"],
                actor=request.user,
                reason=serializer.validated_data.get("reason", ""),
                rework_instructions=serializer.validated_data.get("rework_instructions", ""),
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(QualityInspectionSerializer(inspection, context={"request": request}).data)


class QualityReworkListView(generics.ListAPIView):
    queryset = QualityRework.objects.none()
    serializer_class = QualityReworkSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "status", "manufacturing_operation_id")
    ordering = ("-created_at",)

    def get_queryset(self):
        return scoped_reworks(self.request.user, "quality.inspection.view")


class QualityReworkCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=QualityReworkCompleteSerializer, responses=QualityReworkSerializer)
    def post(self, request, rework_id):
        serializer = QualityReworkCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rework = scoped_reworks(request.user, "quality.rework.manage").get(id=rework_id)
        except QualityRework.DoesNotExist as exc:
            raise NotFound() from exc
        if not has_permission(request.user, "quality.rework.manage", company=rework.company):
            raise PermissionDenied("You cannot complete this quality rework.")
        try:
            rework = complete_rework(
                rework=rework,
                actor=request.user,
                result_notes=serializer.validated_data.get("result_notes", ""),
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(QualityReworkSerializer(rework).data)


class QualitySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=QualitySummarySerializer)
    def get(self, request):
        queryset = scoped_inspections(request.user, "quality.metrics.view")
        company_id = request.query_params.get("company_id")
        inspection_type = request.query_params.get("inspection_type")
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if inspection_type:
            queryset = queryset.filter(inspection_type=inspection_type)
        return Response(QualitySummarySerializer(quality_summary(queryset)).data)
