from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ivadoo.audit.services import audit_snapshot, record_audit_event
from ivadoo.authorization.services import authorized_company_ids, has_permission

from .models import (
    PurchaseOrder,
    PurchaseRequest,
    RequestForQuotation,
    SupplierQuotation,
    SupplierQuotationLine,
)
from .procurement_serializers import (
    PurchaseOrderSerializer,
    PurchaseRequestSerializer,
    QuoteComparisonItemSerializer,
    RequestForQuotationSerializer,
    SupplierQuotationSerializer,
    TransitionSerializer,
)
from .procurement_services import (
    select_supplier_quotation,
    transition_purchase_order,
    transition_purchase_request,
    transition_rfq,
)


def _raise_service_validation(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def _scoped(queryset, user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return queryset.none()
    return queryset.filter(organization_id=user.organization_id, company_id__in=company_ids)


def scoped_purchase_requests(user, permission_code):
    return _scoped(PurchaseRequest.objects.all(), user, permission_code).select_related(
        "company", "establishment", "warehouse", "order", "created_by", "approved_by"
    ).prefetch_related("lines")


def scoped_rfqs(user, permission_code):
    return _scoped(RequestForQuotation.objects.all(), user, permission_code).select_related(
        "company", "purchase_request", "currency", "created_by"
    ).prefetch_related("supplier_links", "supplier_links__supplier", "quotations", "quotations__lines")


def scoped_purchase_orders(user, permission_code):
    return _scoped(PurchaseOrder.objects.all(), user, permission_code).select_related(
        "company", "warehouse", "supplier", "purchase_request", "rfq", "quotation", "currency", "created_by", "approved_by"
    ).prefetch_related("lines")


class PurchaseRequestListCreateView(generics.ListCreateAPIView):
    queryset = PurchaseRequest.objects.none()
    serializer_class = PurchaseRequestSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "establishment_id", "warehouse_id", "order_id", "status")
    search_fields = ("number", "notes")
    ordering_fields = ("number", "needed_by", "created_at", "updated_at")
    ordering = ("-created_at",)

    def get_queryset(self):
        return scoped_purchase_requests(self.request.user, "purchase.request.view")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        establishment = serializer.validated_data.get("establishment")
        if not has_permission(self.request.user, "purchase.request.manage", company=company, establishment=establishment):
            raise PermissionDenied("You cannot manage purchase requests in this scope.")
        with transaction.atomic():
            instance = serializer.save(organization=self.request.user.organization, created_by=self.request.user)
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="purchase.request.create",
                object_instance=instance,
                after=audit_snapshot(instance),
                request=self.request,
            )


class PurchaseRequestDetailView(generics.RetrieveUpdateAPIView):
    queryset = PurchaseRequest.objects.none()
    serializer_class = PurchaseRequestSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "request_id"

    def get_queryset(self):
        permission = "purchase.request.view" if self.request.method == "GET" else "purchase.request.manage"
        return scoped_purchase_requests(self.request.user, permission)

    def perform_update(self, serializer):
        if serializer.instance.status != PurchaseRequest.Status.DRAFT:
            raise ValidationError({"status": "Only draft purchase requests may be edited directly."})
        company = serializer.validated_data.get("company", serializer.instance.company)
        establishment = serializer.validated_data.get("establishment", serializer.instance.establishment)
        if not has_permission(self.request.user, "purchase.request.manage", company=company, establishment=establishment):
            raise PermissionDenied("You cannot manage this purchase request.")
        before = audit_snapshot(serializer.instance)
        with transaction.atomic():
            instance = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="purchase.request.update",
                object_instance=instance,
                before=before,
                after=audit_snapshot(instance),
                request=self.request,
            )


class PurchaseRequestActionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=TransitionSerializer, responses=PurchaseRequestSerializer)
    def post(self, request, request_id):
        action_serializer = TransitionSerializer(data=request.data)
        action_serializer.is_valid(raise_exception=True)
        action = action_serializer.validated_data["action"]
        permission = "purchase.request.approve" if action in {"approve", "reject"} else "purchase.request.manage"
        try:
            instance = scoped_purchase_requests(request.user, permission).get(id=request_id)
        except PurchaseRequest.DoesNotExist as exc:
            raise NotFound() from exc
        if not has_permission(request.user, permission, company=instance.company, establishment=instance.establishment):
            raise PermissionDenied("You cannot perform this purchase request action.")
        try:
            instance = transition_purchase_request(
                purchase_request=instance,
                action=action,
                actor=request.user,
                reason=action_serializer.validated_data.get("reason", ""),
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(PurchaseRequestSerializer(instance, context={"request": request}).data)


class RFQListCreateView(generics.ListCreateAPIView):
    queryset = RequestForQuotation.objects.none()
    serializer_class = RequestForQuotationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "purchase_request_id", "currency_id", "status")
    search_fields = ("number", "notes")
    ordering_fields = ("number", "due_date", "created_at", "updated_at")
    ordering = ("-created_at",)

    def get_queryset(self):
        return scoped_rfqs(self.request.user, "purchase.rfq.view")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        if not has_permission(self.request.user, "purchase.rfq.manage", company=company):
            raise PermissionDenied("You cannot manage RFQs in this company.")
        with transaction.atomic():
            instance = serializer.save(organization=self.request.user.organization, created_by=self.request.user)
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="purchase.rfq.create",
                object_instance=instance,
                after=audit_snapshot(instance),
                company_id=company.id,
                request=self.request,
            )


class RFQDetailView(generics.RetrieveUpdateAPIView):
    queryset = RequestForQuotation.objects.none()
    serializer_class = RequestForQuotationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "rfq_id"

    def get_queryset(self):
        permission = "purchase.rfq.view" if self.request.method == "GET" else "purchase.rfq.manage"
        return scoped_rfqs(self.request.user, permission)

    def perform_update(self, serializer):
        if serializer.instance.status != RequestForQuotation.Status.DRAFT:
            raise ValidationError({"status": "Only draft RFQs may be edited directly."})
        company = serializer.validated_data.get("company", serializer.instance.company)
        if not has_permission(self.request.user, "purchase.rfq.manage", company=company):
            raise PermissionDenied("You cannot manage this RFQ.")
        before = audit_snapshot(serializer.instance)
        with transaction.atomic():
            instance = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="purchase.rfq.update",
                object_instance=instance,
                before=before,
                after=audit_snapshot(instance),
                company_id=company.id,
                request=self.request,
            )


class RFQActionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=TransitionSerializer, responses=RequestForQuotationSerializer)
    def post(self, request, rfq_id):
        action_serializer = TransitionSerializer(data=request.data)
        action_serializer.is_valid(raise_exception=True)
        try:
            instance = scoped_rfqs(request.user, "purchase.rfq.manage").get(id=rfq_id)
        except RequestForQuotation.DoesNotExist as exc:
            raise NotFound() from exc
        try:
            instance = transition_rfq(
                rfq=instance,
                action=action_serializer.validated_data["action"],
                actor=request.user,
                reason=action_serializer.validated_data.get("reason", ""),
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(RequestForQuotationSerializer(instance, context={"request": request}).data)


class SupplierQuotationListCreateView(generics.ListCreateAPIView):
    queryset = SupplierQuotation.objects.none()
    serializer_class = SupplierQuotationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("supplier_id", "status")
    ordering_fields = ("created_at", "quoted_at", "valid_until")
    ordering = ("created_at",)

    def get_rfq(self, permission="purchase.rfq.view"):
        try:
            return scoped_rfqs(self.request.user, permission).get(id=self.kwargs["rfq_id"])
        except RequestForQuotation.DoesNotExist as exc:
            raise NotFound() from exc

    def get_queryset(self):
        rfq = self.get_rfq()
        return SupplierQuotation.objects.filter(rfq=rfq).select_related("supplier", "rfq", "rfq__currency").prefetch_related("lines")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["rfq"] = self.get_rfq("purchase.rfq.manage" if self.request.method == "POST" else "purchase.rfq.view")
        return context

    def perform_create(self, serializer):
        rfq = self.get_rfq("purchase.rfq.manage")
        if rfq.status != RequestForQuotation.Status.SENT:
            raise ValidationError({"rfq": "Supplier quotations may only be recorded for a sent RFQ."})
        with transaction.atomic():
            instance = serializer.save()
            record_audit_event(
                organization=rfq.organization,
                actor=self.request.user,
                action="purchase.quotation.receive",
                object_instance=instance,
                after=audit_snapshot(instance),
                company_id=rfq.company_id,
                request=self.request,
            )


class SupplierQuotationSelectView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses=SupplierQuotationSerializer)
    def post(self, request, rfq_id, quotation_id):
        try:
            rfq = scoped_rfqs(request.user, "purchase.rfq.manage").get(id=rfq_id)
            quotation = SupplierQuotation.objects.select_related("rfq", "supplier").get(id=quotation_id, rfq=rfq)
        except (RequestForQuotation.DoesNotExist, SupplierQuotation.DoesNotExist) as exc:
            raise NotFound() from exc
        try:
            quotation = select_supplier_quotation(quotation=quotation, actor=request.user, request=request)
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(SupplierQuotationSerializer(quotation, context={"request": request, "rfq": rfq}).data)


class RFQComparisonView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=QuoteComparisonItemSerializer(many=True))
    def get(self, request, rfq_id):
        try:
            rfq = scoped_rfqs(request.user, "purchase.rfq.view").get(id=rfq_id)
        except RequestForQuotation.DoesNotExist as exc:
            raise NotFound() from exc
        results = []
        quotations = SupplierQuotation.objects.filter(rfq=rfq).select_related("supplier", "rfq__currency").prefetch_related("lines")
        for quotation in quotations:
            lines = list(quotation.lines.all())
            total = sum((line.quantity * line.unit_price for line in lines), Decimal("0"))
            max_lead = max((line.lead_time_days for line in lines), default=0)
            results.append({
                "quotation_id": quotation.id,
                "supplier_id": quotation.supplier_id,
                "supplier_name": quotation.supplier.name,
                "currency_code": rfq.currency_id,
                "total_amount": total,
                "max_lead_time_days": max_lead,
            })
        results.sort(key=lambda item: (item["total_amount"], item["max_lead_time_days"], item["supplier_name"]))
        return Response(QuoteComparisonItemSerializer(results, many=True).data)


class PurchaseOrderListCreateView(generics.ListCreateAPIView):
    queryset = PurchaseOrder.objects.none()
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "warehouse_id", "supplier_id", "purchase_request_id", "rfq_id", "currency_id", "status")
    search_fields = ("number", "supplier__name", "notes")
    ordering_fields = ("number", "created_at", "updated_at", "ordered_at")
    ordering = ("-created_at",)

    def get_queryset(self):
        return scoped_purchase_orders(self.request.user, "purchase.order.view")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        if not has_permission(self.request.user, "purchase.order.manage", company=company):
            raise PermissionDenied("You cannot manage purchase orders in this company.")
        with transaction.atomic():
            instance = serializer.save(organization=self.request.user.organization, created_by=self.request.user)
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="purchase.order.create",
                object_instance=instance,
                after=audit_snapshot(instance),
                company_id=company.id,
                request=self.request,
            )


class PurchaseOrderDetailView(generics.RetrieveUpdateAPIView):
    queryset = PurchaseOrder.objects.none()
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "purchase_order_id"

    def get_queryset(self):
        permission = "purchase.order.view" if self.request.method == "GET" else "purchase.order.manage"
        return scoped_purchase_orders(self.request.user, permission)

    def perform_update(self, serializer):
        if serializer.instance.status != PurchaseOrder.Status.DRAFT:
            raise ValidationError({"status": "Only draft purchase orders may be edited directly."})
        company = serializer.validated_data.get("company", serializer.instance.company)
        if not has_permission(self.request.user, "purchase.order.manage", company=company):
            raise PermissionDenied("You cannot manage this purchase order.")
        before = audit_snapshot(serializer.instance)
        with transaction.atomic():
            instance = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="purchase.order.update",
                object_instance=instance,
                before=before,
                after=audit_snapshot(instance),
                company_id=company.id,
                request=self.request,
            )


class PurchaseOrderActionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=TransitionSerializer, responses=PurchaseOrderSerializer)
    def post(self, request, purchase_order_id):
        action_serializer = TransitionSerializer(data=request.data)
        action_serializer.is_valid(raise_exception=True)
        action = action_serializer.validated_data["action"]
        permission = "purchase.order.approve" if action == "approve" else "purchase.order.manage"
        try:
            instance = scoped_purchase_orders(request.user, permission).get(id=purchase_order_id)
        except PurchaseOrder.DoesNotExist as exc:
            raise NotFound() from exc
        if not has_permission(request.user, permission, company=instance.company):
            raise PermissionDenied("You cannot perform this purchase order action.")
        try:
            instance = transition_purchase_order(
                purchase_order=instance,
                action=action,
                actor=request.user,
                reason=action_serializer.validated_data.get("reason", ""),
                request=request,
            )
        except DjangoValidationError as exc:
            _raise_service_validation(exc)
        return Response(PurchaseOrderSerializer(instance, context={"request": request}).data)
