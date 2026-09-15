from django.db import transaction
from django.db.models import Q
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

from .models import Customer
from .serializers import CustomerSerializer


def scoped_customers(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    establishment_ids = authorized_establishment_ids(user, permission_code)
    if not company_ids and not establishment_ids:
        return Customer.objects.none()
    return Customer.objects.filter(
        organization_id=user.organization_id
    ).filter(
        Q(company_id__in=company_ids) | Q(establishment_id__in=establishment_ids)
    ).select_related(
        "company", "establishment", "preferred_currency"
    ).prefetch_related("contacts", "addresses", "consents")


class CustomerListView(generics.ListCreateAPIView):
    queryset = Customer.objects.none()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "company_id", "establishment_id", "customer_type", "status",
        "language_code",
    )
    search_fields = (
        "code", "display_name", "first_name", "last_name", "legal_name",
        "email", "phone",
    )
    ordering_fields = ("display_name", "code", "created_at", "updated_at")
    ordering = ("display_name",)

    def get_queryset(self):
        return scoped_customers(self.request.user, "fashion.customer.view")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        establishment = serializer.validated_data.get("establishment")
        if not has_permission(
            self.request.user,
            "fashion.customer.manage",
            company=company,
            establishment=establishment,
        ):
            raise PermissionDenied("You cannot manage customers in this scope.")
        with transaction.atomic():
            customer = serializer.save(organization=self.request.user.organization)
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="fashion.customer.create",
                object_instance=customer,
                after=audit_snapshot(customer),
                request=self.request,
            )


class CustomerDetailView(generics.RetrieveUpdateAPIView):
    queryset = Customer.objects.none()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "customer_id"

    def get_queryset(self):
        permission = (
            "fashion.customer.view"
            if self.request.method == "GET"
            else "fashion.customer.manage"
        )
        return scoped_customers(self.request.user, permission)

    def perform_update(self, serializer):
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            customer = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="fashion.customer.update",
                object_instance=customer,
                before=before,
                after=audit_snapshot(customer),
                request=self.request,
            )
