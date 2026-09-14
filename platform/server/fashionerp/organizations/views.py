from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated

from fashionerp.audit.services import audit_snapshot, record_audit_event
from fashionerp.authorization.services import (
    authorized_company_ids,
    authorized_establishment_ids,
    has_permission,
)

from .models import Company, Establishment, Organization
from .serializers import (
    CompanySerializer,
    EstablishmentSerializer,
    OrganizationSerializer,
)


class OrganizationListView(generics.ListAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        if not has_permission(
            self.request.user,
            "foundation.organization.view",
        ):
            return Organization.objects.none()
        return Organization.objects.filter(pk=self.request.user.organization_id)


class OrganizationDetailView(generics.RetrieveAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "organization_id"

    def get_queryset(self):
        if not has_permission(
            self.request.user,
            "foundation.organization.view",
        ):
            return Organization.objects.none()
        return Organization.objects.filter(pk=self.request.user.organization_id)


class CompanyListView(generics.ListCreateAPIView):
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ("status", "country_code")
    search_fields = ("name", "legal_name", "code")
    ordering_fields = ("name", "code", "created_at")
    ordering = ("name",)

    def get_queryset(self):
        permission_code = (
            "foundation.company.manage"
            if self.request.method != "GET"
            else "foundation.company.view"
        )
        allowed_ids = authorized_company_ids(self.request.user, permission_code)
        return Company.objects.filter(
            organization_id=self.request.user.organization_id,
            id__in=allowed_ids,
        )

    def perform_create(self, serializer):
        if not has_permission(
            self.request.user,
            "foundation.company.manage",
        ):
            raise PermissionDenied(
                "Organization-level company management permission is required."
            )
        with transaction.atomic():
            company = serializer.save(
                organization=self.request.user.organization
            )
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="foundation.company.create",
                object_instance=company,
                after=audit_snapshot(company),
                request=self.request,
            )


class CompanyDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "company_id"

    def get_queryset(self):
        permission_code = (
            "foundation.company.view"
            if self.request.method == "GET"
            else "foundation.company.manage"
        )
        allowed_ids = authorized_company_ids(self.request.user, permission_code)
        return Company.objects.filter(
            organization_id=self.request.user.organization_id,
            id__in=allowed_ids,
        )

    def perform_update(self, serializer):
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            company = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="foundation.company.update",
                object_instance=company,
                before=before,
                after=audit_snapshot(company),
                request=self.request,
            )


class EstablishmentListView(generics.ListCreateAPIView):
    serializer_class = EstablishmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ("company_id", "status", "site_type", "country_code")
    search_fields = ("name", "code", "city", "region")
    ordering_fields = ("name", "code", "created_at")
    ordering = ("name",)

    def get_queryset(self):
        permission_code = (
            "foundation.establishment.manage"
            if self.request.method != "GET"
            else "foundation.establishment.view"
        )
        allowed_ids = authorized_establishment_ids(
            self.request.user,
            permission_code,
        )
        return Establishment.objects.filter(
            company__organization_id=self.request.user.organization_id,
            id__in=allowed_ids,
        ).select_related("company")

    def perform_update(self, serializer):
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            establishment = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="foundation.establishment.update",
                object_instance=establishment,
                before=before,
                after=audit_snapshot(establishment),
                request=self.request,
            )

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        if not has_permission(
            self.request.user,
            "foundation.establishment.manage",
            company=company,
        ):
            raise PermissionDenied(
                "You cannot manage establishments for this company."
            )
        with transaction.atomic():
            establishment = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="foundation.establishment.create",
                object_instance=establishment,
                after=audit_snapshot(establishment),
                request=self.request,
            )


class EstablishmentDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = EstablishmentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "establishment_id"

    def get_queryset(self):
        permission_code = (
            "foundation.establishment.view"
            if self.request.method == "GET"
            else "foundation.establishment.manage"
        )
        allowed_ids = authorized_establishment_ids(
            self.request.user,
            permission_code,
        )
        return Establishment.objects.filter(
            company__organization_id=self.request.user.organization_id,
            id__in=allowed_ids,
        ).select_related("company")
