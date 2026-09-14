from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Organization
from .serializers import OrganizationSerializer


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
