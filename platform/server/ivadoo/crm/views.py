from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ivadoo.audit.services import audit_snapshot, record_audit_event
from ivadoo.authorization.services import (
    authorized_company_ids,
    authorized_establishment_ids,
    has_permission,
)
from ivadoo.organizations.models import Establishment

from .models import (
    CRMConversionEvent,
    CRMLead,
    CRMOpportunity,
    CRMPipelineStage,
    CRMSource,
)
from .serializers import (
    CRMConversionEventSerializer,
    CRMConvertSerializer,
    CRMLeadSerializer,
    CRMOpportunitySerializer,
    CRMPipelineStageSerializer,
    CRMSourceSerializer,
)
from .services import convert_lead, convert_opportunity


CRM_VIEW = "enterprise.crm.view"
CRM_MANAGE = "enterprise.crm.manage"
CRM_CONVERT = "enterprise.crm.convert"


def _company_scope_ids(user, permission_code):
    company_ids = set(authorized_company_ids(user, permission_code))
    establishment_ids = authorized_establishment_ids(user, permission_code)
    if establishment_ids:
        company_ids.update(
            Establishment.objects.filter(id__in=establishment_ids).values_list(
                "company_id", flat=True
            )
        )
    return company_ids


def _scoped_company_records(queryset, user, permission_code):
    company_ids = _company_scope_ids(user, permission_code)
    if not company_ids:
        return queryset.none()
    return queryset.filter(company_id__in=company_ids)


def _scoped_site_records(queryset, user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    establishment_ids = authorized_establishment_ids(user, permission_code)
    if not company_ids and not establishment_ids:
        return queryset.none()
    return queryset.filter(
        Q(company_id__in=company_ids) | Q(establishment_id__in=establishment_ids)
    )


def _assert_scope(user, permission_code, *, company, establishment=None):
    if not has_permission(
        user,
        permission_code,
        company=company,
        establishment=establishment,
    ):
        raise PermissionDenied("You cannot perform this CRM action in the selected scope.")


def _record_change(*, request, action, instance, before=None):
    record_audit_event(
        organization=request.user.organization,
        actor=request.user,
        action=action,
        object_instance=instance,
        before=before,
        after=audit_snapshot(instance),
        request=request,
    )


def _record_conversion(*, request, event):
    record_audit_event(
        organization=request.user.organization,
        actor=request.user,
        action="enterprise.crm.convert",
        object_instance=event,
        after=audit_snapshot(event),
        request=request,
        metadata={
            "source_kind": event.source_kind,
            "lead_id": str(event.lead_id) if event.lead_id else None,
            "opportunity_id": (
                str(event.opportunity_id) if event.opportunity_id else None
            ),
            "customer_id": str(event.customer_id),
            "created_customer": event.created_customer,
        },
    )
    if event.created_customer:
        record_audit_event(
            organization=request.user.organization,
            actor=request.user,
            action="enterprise.crm.customer.create_from_conversion",
            object_instance=event.customer,
            after=audit_snapshot(event.customer),
            request=request,
        )


class CRMSourceListView(generics.ListCreateAPIView):
    queryset = CRMSource.objects.none()
    serializer_class = CRMSourceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ("company_id", "source_type", "is_active")
    search_fields = ("code", "name", "description")
    ordering_fields = ("code", "name", "source_type", "created_at", "updated_at")
    ordering = ("name",)

    def get_queryset(self):
        return _scoped_company_records(
            CRMSource.objects.filter(
                organization_id=self.request.user.organization_id
            ).select_related("company"),
            self.request.user,
            CRM_VIEW,
        )

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        _assert_scope(self.request.user, CRM_MANAGE, company=company)
        with transaction.atomic():
            source = serializer.save(organization=self.request.user.organization)
            _record_change(
                request=self.request,
                action="enterprise.crm.source.create",
                instance=source,
            )


class CRMSourceDetailView(generics.RetrieveUpdateAPIView):
    queryset = CRMSource.objects.none()
    serializer_class = CRMSourceSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "source_id"

    def get_queryset(self):
        return _scoped_company_records(
            CRMSource.objects.filter(organization_id=self.request.user.organization_id),
            self.request.user,
            CRM_VIEW,
        )

    def perform_update(self, serializer):
        company = serializer.validated_data.get("company", serializer.instance.company)
        _assert_scope(self.request.user, CRM_MANAGE, company=company)
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            source = serializer.save()
            _record_change(
                request=self.request,
                action="enterprise.crm.source.update",
                instance=source,
                before=before,
            )


class CRMPipelineStageListView(generics.ListCreateAPIView):
    queryset = CRMPipelineStage.objects.none()
    serializer_class = CRMPipelineStageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ("company_id", "stage_type", "is_active")
    search_fields = ("code", "name")
    ordering_fields = ("position", "name", "probability", "created_at", "updated_at")
    ordering = ("position", "name")

    def get_queryset(self):
        return _scoped_company_records(
            CRMPipelineStage.objects.filter(
                organization_id=self.request.user.organization_id
            ).select_related("company"),
            self.request.user,
            CRM_VIEW,
        )

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        _assert_scope(self.request.user, CRM_MANAGE, company=company)
        with transaction.atomic():
            stage = serializer.save(organization=self.request.user.organization)
            _record_change(
                request=self.request,
                action="enterprise.crm.stage.create",
                instance=stage,
            )


class CRMPipelineStageDetailView(generics.RetrieveUpdateAPIView):
    queryset = CRMPipelineStage.objects.none()
    serializer_class = CRMPipelineStageSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "stage_id"

    def get_queryset(self):
        return _scoped_company_records(
            CRMPipelineStage.objects.filter(
                organization_id=self.request.user.organization_id
            ),
            self.request.user,
            CRM_VIEW,
        )

    def perform_update(self, serializer):
        company = serializer.validated_data.get("company", serializer.instance.company)
        _assert_scope(self.request.user, CRM_MANAGE, company=company)
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            stage = serializer.save()
            _record_change(
                request=self.request,
                action="enterprise.crm.stage.update",
                instance=stage,
                before=before,
            )


class CRMLeadListView(generics.ListCreateAPIView):
    queryset = CRMLead.objects.none()
    serializer_class = CRMLeadSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "company_id",
        "establishment_id",
        "source_id",
        "owner_id",
        "prospect_type",
        "status",
    )
    search_fields = (
        "code",
        "display_name",
        "first_name",
        "last_name",
        "legal_name",
        "email",
        "phone",
        "notes",
    )
    ordering_fields = ("display_name", "status", "created_at", "updated_at")
    ordering = ("-created_at",)

    def get_queryset(self):
        return _scoped_site_records(
            CRMLead.objects.filter(
                organization_id=self.request.user.organization_id
            ).select_related(
                "company",
                "establishment",
                "source",
                "owner",
                "converted_customer",
                "converted_by",
                "created_by",
            ),
            self.request.user,
            CRM_VIEW,
        )

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        establishment = serializer.validated_data.get("establishment")
        _assert_scope(
            self.request.user,
            CRM_MANAGE,
            company=company,
            establishment=establishment,
        )
        with transaction.atomic():
            lead = serializer.save(
                organization=self.request.user.organization,
                created_by=self.request.user,
            )
            _record_change(
                request=self.request,
                action="enterprise.crm.lead.create",
                instance=lead,
            )


class CRMLeadDetailView(generics.RetrieveUpdateAPIView):
    queryset = CRMLead.objects.none()
    serializer_class = CRMLeadSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "lead_id"

    def get_queryset(self):
        return _scoped_site_records(
            CRMLead.objects.filter(organization_id=self.request.user.organization_id),
            self.request.user,
            CRM_VIEW,
        )

    def perform_update(self, serializer):
        company = serializer.validated_data.get("company", serializer.instance.company)
        establishment = serializer.validated_data.get(
            "establishment", serializer.instance.establishment
        )
        _assert_scope(
            self.request.user,
            CRM_MANAGE,
            company=company,
            establishment=establishment,
        )
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            lead = serializer.save()
            _record_change(
                request=self.request,
                action="enterprise.crm.lead.update",
                instance=lead,
                before=before,
            )


class CRMLeadConvertView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CRMConvertSerializer

    def post(self, request, lead_id):
        lead = generics.get_object_or_404(
            _scoped_site_records(
                CRMLead.objects.filter(
                    organization_id=request.user.organization_id
                ).select_related("company", "establishment"),
                request.user,
                CRM_CONVERT,
            ),
            id=lead_id,
        )
        _assert_scope(
            request.user,
            CRM_CONVERT,
            company=lead.company,
            establishment=lead.establishment,
        )
        serializer = CRMConvertSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        event = convert_lead(
            lead=lead,
            actor=request.user,
            **serializer.validated_data,
        )
        event = CRMConversionEvent.objects.select_related("customer").get(pk=event.pk)
        _record_conversion(request=request, event=event)
        return Response(
            CRMConversionEventSerializer(event).data,
            status=status.HTTP_200_OK,
        )


class CRMOpportunityListView(generics.ListCreateAPIView):
    queryset = CRMOpportunity.objects.none()
    serializer_class = CRMOpportunitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "company_id",
        "establishment_id",
        "lead_id",
        "customer_id",
        "source_id",
        "stage_id",
        "owner_id",
        "prospect_type",
        "currency_id",
    )
    search_fields = (
        "code",
        "title",
        "description",
        "contact_name",
        "legal_name",
        "email",
        "phone",
    )
    ordering_fields = (
        "title",
        "expected_revenue",
        "probability",
        "expected_close_date",
        "created_at",
        "updated_at",
    )
    ordering = ("stage__position", "-created_at")

    def get_queryset(self):
        return _scoped_site_records(
            CRMOpportunity.objects.filter(
                organization_id=self.request.user.organization_id
            ).select_related(
                "company",
                "establishment",
                "lead",
                "customer",
                "source",
                "stage",
                "owner",
                "currency",
                "converted_by",
                "created_by",
            ),
            self.request.user,
            CRM_VIEW,
        )

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        establishment = serializer.validated_data.get("establishment")
        _assert_scope(
            self.request.user,
            CRM_MANAGE,
            company=company,
            establishment=establishment,
        )
        with transaction.atomic():
            opportunity = serializer.save(
                organization=self.request.user.organization,
                created_by=self.request.user,
            )
            _record_change(
                request=self.request,
                action="enterprise.crm.opportunity.create",
                instance=opportunity,
            )


class CRMOpportunityDetailView(generics.RetrieveUpdateAPIView):
    queryset = CRMOpportunity.objects.none()
    serializer_class = CRMOpportunitySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "opportunity_id"

    def get_queryset(self):
        return _scoped_site_records(
            CRMOpportunity.objects.filter(
                organization_id=self.request.user.organization_id
            ),
            self.request.user,
            CRM_VIEW,
        )

    def perform_update(self, serializer):
        company = serializer.validated_data.get("company", serializer.instance.company)
        establishment = serializer.validated_data.get(
            "establishment", serializer.instance.establishment
        )
        _assert_scope(
            self.request.user,
            CRM_MANAGE,
            company=company,
            establishment=establishment,
        )
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            opportunity = serializer.save()
            _record_change(
                request=self.request,
                action="enterprise.crm.opportunity.update",
                instance=opportunity,
                before=before,
            )


class CRMOpportunityConvertView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CRMConvertSerializer

    def post(self, request, opportunity_id):
        opportunity = generics.get_object_or_404(
            _scoped_site_records(
                CRMOpportunity.objects.filter(
                    organization_id=request.user.organization_id
                ).select_related("company", "establishment"),
                request.user,
                CRM_CONVERT,
            ),
            id=opportunity_id,
        )
        _assert_scope(
            request.user,
            CRM_CONVERT,
            company=opportunity.company,
            establishment=opportunity.establishment,
        )
        serializer = CRMConvertSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        event = convert_opportunity(
            opportunity=opportunity,
            actor=request.user,
            **serializer.validated_data,
        )
        event = CRMConversionEvent.objects.select_related("customer").get(pk=event.pk)
        _record_conversion(request=request, event=event)
        return Response(
            CRMConversionEventSerializer(event).data,
            status=status.HTTP_200_OK,
        )


class CRMConversionEventListView(generics.ListAPIView):
    queryset = CRMConversionEvent.objects.none()
    serializer_class = CRMConversionEventSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = (
        "company_id",
        "establishment_id",
        "source_kind",
        "lead_id",
        "opportunity_id",
        "customer_id",
        "created_customer",
        "actor_id",
    )
    ordering_fields = ("occurred_at",)
    ordering = ("-occurred_at",)

    def get_queryset(self):
        return _scoped_site_records(
            CRMConversionEvent.objects.filter(
                organization_id=self.request.user.organization_id
            ).select_related(
                "company",
                "establishment",
                "lead",
                "opportunity",
                "customer",
                "actor",
            ),
            self.request.user,
            CRM_VIEW,
        )
