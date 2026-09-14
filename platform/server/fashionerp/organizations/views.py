from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated

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
        organization_id = getattr(self.request.user, "organization_id", None)
        if organization_id is None:
            return Organization.objects.none()
        return Organization.objects.filter(pk=organization_id)


class OrganizationDetailView(generics.RetrieveAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "organization_id"

    def get_queryset(self):
        organization_id = getattr(self.request.user, "organization_id", None)
        if organization_id is None:
            return Organization.objects.none()
        return Organization.objects.filter(pk=organization_id)


class CompanyListView(generics.ListAPIView):
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ("status", "country_code")
    search_fields = ("name", "legal_name", "code")
    ordering_fields = ("name", "code", "created_at")
    ordering = ("name",)

    def get_queryset(self):
        organization_id = getattr(self.request.user, "organization_id", None)
        if organization_id is None:
            return Company.objects.none()
        return Company.objects.filter(organization_id=organization_id)


class CompanyDetailView(generics.RetrieveAPIView):
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "company_id"

    def get_queryset(self):
        organization_id = getattr(self.request.user, "organization_id", None)
        if organization_id is None:
            return Company.objects.none()
        return Company.objects.filter(organization_id=organization_id)


class EstablishmentListView(generics.ListAPIView):
    serializer_class = EstablishmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ("company_id", "status", "site_type", "country_code")
    search_fields = ("name", "code", "city", "region")
    ordering_fields = ("name", "code", "created_at")
    ordering = ("name",)

    def get_queryset(self):
        organization_id = getattr(self.request.user, "organization_id", None)
        if organization_id is None:
            return Establishment.objects.none()
        return Establishment.objects.filter(
            company__organization_id=organization_id
        ).select_related("company")


class EstablishmentDetailView(generics.RetrieveAPIView):
    serializer_class = EstablishmentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "establishment_id"

    def get_queryset(self):
        organization_id = getattr(self.request.user, "organization_id", None)
        if organization_id is None:
            return Establishment.objects.none()
        return Establishment.objects.filter(
            company__organization_id=organization_id
        ).select_related("company")
