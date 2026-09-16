from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated

from ivadoo.audit.services import record_audit_event

from .tracking_models import (
    CRMFollowUp,
    CRMInteraction,
    CRMSegment,
    CRMSegmentMembership,
)
from .tracking_serializers import (
    CRMFollowUpSerializer,
    CRMInteractionSerializer,
    CRMSegmentMembershipSerializer,
    CRMSegmentSerializer,
)
from .views import (
    CRM_MANAGE,
    CRM_VIEW,
    _assert_scope,
    _scoped_company_records,
    _scoped_site_records,
)


def _json_safe(value):
    if isinstance(value, (UUID, datetime, date, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _tracking_snapshot(instance):
    snapshot = {}
    for field in instance._meta.concrete_fields:
        key = field.attname
        snapshot[key] = _json_safe(getattr(instance, key))
    return snapshot


def _record_tracking_change(*, request, action, instance, before=None, after=True):
    record_audit_event(
        organization=request.user.organization,
        actor=request.user,
        action=action,
        object_instance=instance,
        company_id=instance.company_id,
        establishment_id=getattr(instance, "establishment_id", None),
        before=before,
        after=_tracking_snapshot(instance) if after else None,
        request=request,
    )


def _customer_history_filter(queryset, customer_id):
    if not customer_id:
        return queryset
    return queryset.filter(
        Q(customer_id=customer_id)
        | Q(lead__converted_customer_id=customer_id)
        | Q(opportunity__customer_id=customer_id)
        | Q(opportunity__lead__converted_customer_id=customer_id)
    ).distinct()


class CRMSegmentListView(generics.ListCreateAPIView):
    queryset = CRMSegment.objects.none()
    serializer_class = CRMSegmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ("company_id", "is_active")
    search_fields = ("code", "name", "description")
    ordering_fields = ("code", "name", "created_at", "updated_at")
    ordering = ("name",)

    def get_queryset(self):
        return _scoped_company_records(
            CRMSegment.objects.filter(organization_id=self.request.user.organization_id),
            self.request.user,
            CRM_VIEW,
        )

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        _assert_scope(self.request.user, CRM_MANAGE, company=company)
        with transaction.atomic():
            segment = serializer.save(organization=self.request.user.organization)
            _record_tracking_change(
                request=self.request,
                action="enterprise.crm.segment.create",
                instance=segment,
            )


class CRMSegmentDetailView(generics.RetrieveUpdateAPIView):
    queryset = CRMSegment.objects.none()
    serializer_class = CRMSegmentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "segment_id"

    def get_queryset(self):
        return _scoped_company_records(
            CRMSegment.objects.filter(organization_id=self.request.user.organization_id),
            self.request.user,
            CRM_VIEW,
        )

    def perform_update(self, serializer):
        company = serializer.validated_data.get("company", serializer.instance.company)
        _assert_scope(self.request.user, CRM_MANAGE, company=company)
        with transaction.atomic():
            before = _tracking_snapshot(serializer.instance)
            segment = serializer.save()
            _record_tracking_change(
                request=self.request,
                action="enterprise.crm.segment.update",
                instance=segment,
                before=before,
            )


class CRMSegmentMembershipListView(generics.ListCreateAPIView):
    queryset = CRMSegmentMembership.objects.none()
    serializer_class = CRMSegmentMembershipSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ("company_id", "segment_id", "lead_id", "added_by_id")
    ordering_fields = ("added_at",)
    ordering = ("-added_at",)

    def get_queryset(self):
        queryset = _scoped_company_records(
            CRMSegmentMembership.objects.filter(
                organization_id=self.request.user.organization_id
            ).select_related("company", "segment", "lead", "customer", "added_by"),
            self.request.user,
            CRM_VIEW,
        )
        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            queryset = queryset.filter(
                Q(customer_id=customer_id) | Q(lead__converted_customer_id=customer_id)
            ).distinct()
        return queryset

    def perform_create(self, serializer):
        segment = serializer.validated_data["segment"]
        company = segment.company
        _assert_scope(self.request.user, CRM_MANAGE, company=company)
        with transaction.atomic():
            membership = serializer.save(
                organization=self.request.user.organization,
                company=company,
                added_by=self.request.user,
            )
            _record_tracking_change(
                request=self.request,
                action="enterprise.crm.segment_membership.create",
                instance=membership,
            )


class CRMSegmentMembershipDetailView(generics.DestroyAPIView):
    queryset = CRMSegmentMembership.objects.none()
    serializer_class = CRMSegmentMembershipSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "membership_id"

    def get_queryset(self):
        return _scoped_company_records(
            CRMSegmentMembership.objects.filter(organization_id=self.request.user.organization_id),
            self.request.user,
            CRM_VIEW,
        )

    def perform_destroy(self, instance):
        _assert_scope(self.request.user, CRM_MANAGE, company=instance.company)
        with transaction.atomic():
            before = _tracking_snapshot(instance)
            _record_tracking_change(
                request=self.request,
                action="enterprise.crm.segment_membership.delete",
                instance=instance,
                before=before,
                after=False,
            )
            instance.delete()


class CRMFollowUpListView(generics.ListCreateAPIView):
    queryset = CRMFollowUp.objects.none()
    serializer_class = CRMFollowUpSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "company_id", "establishment_id", "lead_id", "opportunity_id", "assignee_id",
        "status", "priority",
    )
    search_fields = ("subject", "description")
    ordering_fields = ("due_at", "status", "priority", "created_at", "updated_at")
    ordering = ("status", "due_at")

    def get_queryset(self):
        queryset = _scoped_site_records(
            CRMFollowUp.objects.filter(
                organization_id=self.request.user.organization_id
            ).select_related(
                "company", "establishment", "lead", "opportunity", "customer",
                "assignee", "created_by",
            ),
            self.request.user,
            CRM_VIEW,
        )
        return _customer_history_filter(queryset, self.request.query_params.get("customer_id"))

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        establishment = serializer.validated_data.get("establishment")
        _assert_scope(
            self.request.user,
            CRM_MANAGE,
            company=company,
            establishment=establishment,
        )
        assignee = serializer.validated_data.get("assignee")
        if assignee is None:
            lead = serializer.validated_data.get("lead")
            opportunity = serializer.validated_data.get("opportunity")
            assignee = getattr(lead or opportunity, "owner", None) or self.request.user
        with transaction.atomic():
            followup = serializer.save(
                organization=self.request.user.organization,
                assignee=assignee,
                created_by=self.request.user,
            )
            _record_tracking_change(
                request=self.request,
                action="enterprise.crm.followup.create",
                instance=followup,
            )


class CRMFollowUpDetailView(generics.RetrieveUpdateAPIView):
    queryset = CRMFollowUp.objects.none()
    serializer_class = CRMFollowUpSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "followup_id"

    def get_queryset(self):
        return _scoped_site_records(
            CRMFollowUp.objects.filter(organization_id=self.request.user.organization_id),
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
            before = _tracking_snapshot(serializer.instance)
            followup = serializer.save()
            _record_tracking_change(
                request=self.request,
                action="enterprise.crm.followup.update",
                instance=followup,
                before=before,
            )


class CRMInteractionListView(generics.ListCreateAPIView):
    queryset = CRMInteraction.objects.none()
    serializer_class = CRMInteractionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "company_id", "establishment_id", "lead_id", "opportunity_id", "actor_id",
        "interaction_type", "channel", "direction",
    )
    search_fields = ("subject", "summary")
    ordering_fields = ("occurred_at", "created_at")
    ordering = ("-occurred_at",)

    def get_queryset(self):
        queryset = _scoped_site_records(
            CRMInteraction.objects.filter(
                organization_id=self.request.user.organization_id
            ).select_related(
                "company", "establishment", "lead", "opportunity", "customer", "actor"
            ),
            self.request.user,
            CRM_VIEW,
        )
        return _customer_history_filter(queryset, self.request.query_params.get("customer_id"))

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
            interaction = serializer.save(
                organization=self.request.user.organization,
                actor=self.request.user,
            )
            _record_tracking_change(
                request=self.request,
                action="enterprise.crm.interaction.create",
                instance=interaction,
            )
