from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ivadoo.audit.services import audit_snapshot
from ivadoo.authorization.services import (
    authorized_company_ids,
    authorized_establishment_ids,
    has_permission,
)

from .models import CommissionCalculation, CommissionRule, ProductivitySnapshot
from .performance_serializers import (
    CommissionCalculateSerializer,
    CommissionCalculationSerializer,
    CommissionRuleSerializer,
    ProductivityGenerateSerializer,
    ProductivitySnapshotSerializer,
)
from .performance_services import calculate_commission, generate_productivity_snapshot
from .views import record_change


PERFORMANCE_VIEW = "enterprise.employee.performance.view"
PERFORMANCE_MANAGE = "enterprise.employee.performance.manage"
COMMISSION_VIEW = "enterprise.employee.commission.view"
COMMISSION_MANAGE = "enterprise.employee.commission.manage"


def _scoped_queryset(queryset, user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    establishment_ids = authorized_establishment_ids(user, permission_code)
    if not company_ids and not establishment_ids:
        return queryset.none()
    return queryset.filter(
        Q(company_id__in=company_ids)
        | Q(establishment_id__in=establishment_ids)
        | Q(workshop_id__in=establishment_ids)
    )


def _assert_scope(user, permission_code, *, company, establishment=None, workshop=None):
    target_site = workshop or establishment
    if not has_permission(
        user,
        permission_code,
        company=company,
        establishment=target_site,
    ):
        raise PermissionDenied("You cannot perform this action in the selected scope.")


class ProductivitySnapshotListView(generics.ListAPIView):
    queryset = ProductivitySnapshot.objects.none()
    serializer_class = ProductivitySnapshotSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "employee_id",
        "company_id",
        "establishment_id",
        "workshop_id",
        "period_start",
        "period_end",
        "formula_version",
    )
    search_fields = ("employee__display_name", "employee__code")
    ordering_fields = ("period_start", "period_end", "generated_at")
    ordering = ("-period_end", "employee__display_name")

    def get_queryset(self):
        return _scoped_queryset(
            ProductivitySnapshot.objects.filter(
                employee__organization_id=self.request.user.organization_id
            ).select_related(
                "employee",
                "company",
                "establishment",
                "workshop",
                "generated_by",
            ),
            self.request.user,
            PERFORMANCE_VIEW,
        )


class ProductivityGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ProductivityGenerateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        _assert_scope(
            request.user,
            PERFORMANCE_MANAGE,
            company=values["company"],
            establishment=values.get("establishment"),
            workshop=values.get("workshop"),
        )
        snapshot = generate_productivity_snapshot(
            **values,
            generated_by=request.user,
        )
        record_change(
            request=request,
            action="enterprise.employee_productivity.generate",
            instance=snapshot,
        )
        return Response(
            ProductivitySnapshotSerializer(snapshot).data,
            status=status.HTTP_201_CREATED,
        )


class CommissionRuleListView(generics.ListCreateAPIView):
    queryset = CommissionRule.objects.none()
    serializer_class = CommissionRuleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "company_id",
        "establishment_id",
        "workshop_id",
        "employee_id",
        "basis",
        "currency_id",
        "is_active",
    )
    search_fields = ("code", "name", "notes", "employee__display_name")
    ordering_fields = ("code", "name", "active_from", "active_until", "created_at")
    ordering = ("company__name", "code")

    def get_queryset(self):
        permission = COMMISSION_VIEW if self.request.method == "GET" else COMMISSION_MANAGE
        return _scoped_queryset(
            CommissionRule.objects.filter(
                organization_id=self.request.user.organization_id
            ).select_related(
                "company",
                "establishment",
                "workshop",
                "employee",
                "currency",
                "created_by",
            ),
            self.request.user,
            permission,
        )

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        establishment = serializer.validated_data.get("establishment")
        workshop = serializer.validated_data.get("workshop")
        _assert_scope(
            self.request.user,
            COMMISSION_MANAGE,
            company=company,
            establishment=establishment,
            workshop=workshop,
        )
        with transaction.atomic():
            rule = serializer.save(
                organization=self.request.user.organization,
                created_by=self.request.user,
            )
            record_change(
                request=self.request,
                action="enterprise.employee_commission_rule.create",
                instance=rule,
            )


class CommissionRuleDetailView(generics.RetrieveUpdateAPIView):
    queryset = CommissionRule.objects.none()
    serializer_class = CommissionRuleSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "rule_id"

    def get_queryset(self):
        permission = COMMISSION_VIEW if self.request.method == "GET" else COMMISSION_MANAGE
        return _scoped_queryset(
            CommissionRule.objects.filter(
                organization_id=self.request.user.organization_id
            ),
            self.request.user,
            permission,
        )

    def perform_update(self, serializer):
        company = serializer.validated_data.get("company", serializer.instance.company)
        establishment = serializer.validated_data.get(
            "establishment", serializer.instance.establishment
        )
        workshop = serializer.validated_data.get("workshop", serializer.instance.workshop)
        _assert_scope(
            self.request.user,
            COMMISSION_MANAGE,
            company=company,
            establishment=establishment,
            workshop=workshop,
        )
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            rule = serializer.save()
            record_change(
                request=self.request,
                action="enterprise.employee_commission_rule.update",
                instance=rule,
                before=before,
            )


class CommissionCalculationListView(generics.ListAPIView):
    queryset = CommissionCalculation.objects.none()
    serializer_class = CommissionCalculationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "rule_id",
        "employee_id",
        "company_id",
        "establishment_id",
        "workshop_id",
        "period_start",
        "period_end",
        "currency_id",
        "formula_version",
    )
    search_fields = (
        "employee__display_name",
        "employee__code",
        "rule__code",
        "rule__name",
    )
    ordering_fields = ("period_start", "period_end", "amount", "generated_at")
    ordering = ("-period_end", "employee__display_name")

    def get_queryset(self):
        return _scoped_queryset(
            CommissionCalculation.objects.filter(
                employee__organization_id=self.request.user.organization_id
            ).select_related(
                "rule",
                "employee",
                "company",
                "establishment",
                "workshop",
                "currency",
                "generated_by",
            ),
            self.request.user,
            COMMISSION_VIEW,
        )


class CommissionCalculateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CommissionCalculateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        rule = values["rule"]
        _assert_scope(
            request.user,
            COMMISSION_MANAGE,
            company=rule.company,
            establishment=rule.establishment,
            workshop=rule.workshop,
        )
        calculation = calculate_commission(
            **values,
            generated_by=request.user,
        )
        record_change(
            request=request,
            action="enterprise.employee_commission.calculate",
            instance=calculation,
        )
        return Response(
            CommissionCalculationSerializer(calculation).data,
            status=status.HTTP_201_CREATED,
        )
