from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ivadoo.audit.services import audit_snapshot, record_audit_event
from ivadoo.authorization.services import authorized_company_ids, has_permission

from .models import ApprovalRule, StockMovementApproval
from .serializers import ApprovalDecisionSerializer, ApprovalRuleSerializer, StockApprovalCreateSerializer, StockApprovalSerializer
from .services import decide_stock_movement_approval


def _raise_service_validation(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def scoped_approval_rules(user, permission_code):
    queryset = ApprovalRule.objects.filter(organization_id=user.organization_id)
    if has_permission(user, permission_code):
        return queryset.select_related("company", "establishment", "warehouse")
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return ApprovalRule.objects.none()
    return queryset.filter(company_id__in=company_ids).select_related("company", "establishment", "warehouse")


class ApprovalRuleListCreateView(generics.ListCreateAPIView):
    queryset = ApprovalRule.objects.none()
    serializer_class = ApprovalRuleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("resource", "action", "company_id", "establishment_id", "warehouse_id", "is_active")
    ordering = ("resource", "action", "-threshold")

    def get_queryset(self):
        permission = "operations.approval.view" if self.request.method == "GET" else "operations.approval.manage"
        return scoped_approval_rules(self.request.user, permission)

    def perform_create(self, serializer):
        company = serializer.validated_data.get("company")
        establishment = serializer.validated_data.get("establishment")
        if not has_permission(self.request.user, "operations.approval.manage", company=company, establishment=establishment):
            raise PermissionDenied("You cannot manage approval rules in this scope.")
        try:
            with transaction.atomic():
                rule = serializer.save(organization=self.request.user.organization)
                rule.full_clean()
                rule.save()
                record_audit_event(
                    organization=self.request.user.organization,
                    actor=self.request.user,
                    action="operations.approval_rule.create",
                    object_instance=rule,
                    after=audit_snapshot(rule),
                    company_id=rule.company_id,
                    request=self.request,
                )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)


class ApprovalRuleDetailView(generics.RetrieveUpdateAPIView):
    queryset = ApprovalRule.objects.none()
    serializer_class = ApprovalRuleSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "rule_id"

    def get_queryset(self):
        permission = "operations.approval.view" if self.request.method == "GET" else "operations.approval.manage"
        return scoped_approval_rules(self.request.user, permission)

    def perform_update(self, serializer):
        instance = serializer.instance
        company = serializer.validated_data.get("company", instance.company)
        establishment = serializer.validated_data.get("establishment", instance.establishment)
        if not has_permission(self.request.user, "operations.approval.manage", company=company, establishment=establishment):
            raise PermissionDenied("You cannot manage this approval rule.")
        before = audit_snapshot(instance)
        try:
            with transaction.atomic():
                rule = serializer.save()
                rule.full_clean()
                rule.save()
                record_audit_event(
                    organization=self.request.user.organization,
                    actor=self.request.user,
                    action="operations.approval_rule.update",
                    object_instance=rule,
                    before=before,
                    after=audit_snapshot(rule),
                    company_id=rule.company_id,
                    request=self.request,
                )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)


class StockApprovalListCreateView(generics.ListCreateAPIView):
    queryset = StockMovementApproval.objects.none()
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "warehouse_id", "movement_type", "status")
    ordering = ("-created_at",)

    def get_serializer_class(self):
        return StockApprovalCreateSerializer if self.request.method == "POST" else StockApprovalSerializer

    def get_queryset(self):
        company_ids = authorized_company_ids(self.request.user, "operations.approval.view")
        return StockMovementApproval.objects.filter(
            organization_id=self.request.user.organization_id,
            company_id__in=company_ids,
        ).select_related("company", "establishment", "warehouse", "requested_by", "decided_by")

    def perform_create(self, serializer):
        data = serializer.validated_data
        location = data.get("source_location") or data.get("destination_location")
        if not has_permission(
            self.request.user,
            "inventory.stock.manage",
            company=location.warehouse.company,
            establishment=location.warehouse.establishment,
        ):
            raise PermissionDenied("You cannot request stock approval in this scope.")
        try:
            serializer.save()
        except DjangoValidationError as exc:
            _raise_service_validation(exc)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(StockApprovalSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)


@extend_schema(request=ApprovalDecisionSerializer, responses={200: StockApprovalSerializer})
class StockApprovalDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, approval_id):
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company_ids = authorized_company_ids(request.user, "operations.approval.approve")
        try:
            approval = StockMovementApproval.objects.select_related("company", "establishment", "warehouse").get(
                id=approval_id,
                organization_id=request.user.organization_id,
                company_id__in=company_ids,
            )
        except StockMovementApproval.DoesNotExist as exc:
            raise NotFound() from exc
        if not has_permission(
            request.user,
            "operations.approval.approve",
            company=approval.company,
            establishment=approval.establishment,
        ):
            raise PermissionDenied("You cannot decide this approval.")
        try:
            approval = decide_stock_movement_approval(
                approval=approval,
                actor=request.user,
                decision=serializer.validated_data["decision"],
                reason=serializer.validated_data.get("reason", ""),
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(StockApprovalSerializer(approval).data)