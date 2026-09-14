from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.filters import OrderingFilter, SearchFilter

from .models import AuditEvent
from .permissions import CanViewAudit
from .serializers import AuditEventSerializer


class AuditEventListView(generics.ListAPIView):
    serializer_class = AuditEventSerializer
    permission_classes = [CanViewAudit]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "action",
        "result",
        "actor_id",
        "company_id",
        "establishment_id",
        "object_type",
        "object_id",
    )
    search_fields = (
        "actor_login",
        "action",
        "object_type",
        "object_label",
        "request_id",
    )
    ordering_fields = ("occurred_at", "action", "actor_login")
    ordering = ("-occurred_at",)

    def get_queryset(self):
        return AuditEvent.objects.filter(
            organization_id=self.request.user.organization_id
        )
