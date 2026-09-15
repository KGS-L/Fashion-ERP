from django.db.models import Q
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from ivadoo.audit.services import audit_snapshot, record_audit_event
from ivadoo.authorization.services import (
    authorized_company_ids, authorized_establishment_ids, has_permission,
)

from .models import MeasurementSet
from .serializers import MeasurementSetSerializer


def scoped_measurement_sets(user):
    company_ids = authorized_company_ids(user, "fashion.customer.view")
    establishment_ids = authorized_establishment_ids(user, "fashion.customer.view")
    if not company_ids and not establishment_ids:
        return MeasurementSet.objects.none()
    return MeasurementSet.objects.filter(
        organization_id=user.organization_id
    ).filter(
        Q(company_id__in=company_ids) | Q(establishment_id__in=establishment_ids)
    ).select_related(
        "customer", "company", "establishment", "profile", "created_by"
    ).prefetch_related("values", "values__definition")


class MeasurementSetListCreateView(generics.ListCreateAPIView):
    queryset = MeasurementSet.objects.none()
    serializer_class = MeasurementSetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = scoped_measurement_sets(self.request.user)
        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset

    def perform_create(self, serializer):
        customer = serializer.validated_data["customer"]
        company = serializer.validated_data["company"]
        establishment = serializer.validated_data.get("establishment")
        if customer.organization_id != self.request.user.organization_id or not has_permission(
            self.request.user, "fashion.customer.manage",
            company=company, establishment=establishment,
        ):
            raise PermissionDenied("You cannot record measurements in this customer scope.")
        measurement_set = serializer.save(
            organization=self.request.user.organization,
            created_by=self.request.user,
        )
        record_audit_event(
            organization=self.request.user.organization,
            actor=self.request.user,
            action="fashion.measurement.create",
            object_instance=measurement_set,
            after=audit_snapshot(measurement_set),
            request=self.request,
        )


class MeasurementSetDetailView(generics.RetrieveAPIView):
    queryset = MeasurementSet.objects.none()
    serializer_class = MeasurementSetSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "measurement_set_id"

    def get_queryset(self):
        return scoped_measurement_sets(self.request.user)
