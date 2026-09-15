from django.db import transaction
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated

from ivadoo.audit.services import audit_snapshot, record_audit_event
from ivadoo.authorization.services import authorized_company_ids, has_permission

from .models import Supplier, SupplierAddress, SupplierContact, SupplierProduct
from .serializers import SupplierAddressSerializer, SupplierContactSerializer, SupplierProductSerializer, SupplierSerializer


def scoped_suppliers(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return Supplier.objects.none()
    return Supplier.objects.filter(organization_id=user.organization_id, company_id__in=company_ids).select_related("company", "currency").prefetch_related("contacts", "addresses", "products")


class SupplierListCreateView(generics.ListCreateAPIView):
    queryset = Supplier.objects.none()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "status", "currency_id", "language_code")
    search_fields = ("code", "name", "legal_name", "tax_identifier", "email", "phone")
    ordering_fields = ("name", "code", "lead_time_days", "created_at", "updated_at")
    ordering = ("name",)

    def get_queryset(self):
        return scoped_suppliers(self.request.user, "purchase.supplier.view")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        if not has_permission(self.request.user, "purchase.supplier.manage", company=company):
            raise PermissionDenied("You cannot manage suppliers in this company.")
        with transaction.atomic():
            supplier = serializer.save(organization=self.request.user.organization)
            record_audit_event(organization=self.request.user.organization, actor=self.request.user, action="purchase.supplier.create", object_instance=supplier, after=audit_snapshot(supplier), request=self.request)


class SupplierDetailView(generics.RetrieveUpdateAPIView):
    queryset = Supplier.objects.none()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "supplier_id"

    def get_queryset(self):
        permission = "purchase.supplier.view" if self.request.method == "GET" else "purchase.supplier.manage"
        return scoped_suppliers(self.request.user, permission)

    def perform_update(self, serializer):
        company = serializer.validated_data.get("company", serializer.instance.company)
        if not has_permission(self.request.user, "purchase.supplier.manage", company=company):
            raise PermissionDenied("You cannot manage this supplier.")
        before = audit_snapshot(serializer.instance)
        with transaction.atomic():
            supplier = serializer.save()
            record_audit_event(organization=self.request.user.organization, actor=self.request.user, action="purchase.supplier.update", object_instance=supplier, before=before, after=audit_snapshot(supplier), request=self.request)


class SupplierChildMixin:
    parent_permission = "purchase.supplier.view"
    manage_permission = "purchase.supplier.manage"

    def get_supplier(self, permission_code=None):
        try:
            return scoped_suppliers(self.request.user, permission_code or self.parent_permission).get(id=self.kwargs["supplier_id"])
        except Supplier.DoesNotExist as exc:
            raise NotFound() from exc

    def perform_create(self, serializer):
        supplier = self.get_supplier(self.manage_permission)
        if not has_permission(self.request.user, self.manage_permission, company=supplier.company):
            raise PermissionDenied("You cannot manage this supplier.")
        with transaction.atomic():
            instance = serializer.save(supplier=supplier)
            record_audit_event(organization=self.request.user.organization, actor=self.request.user, action=f"purchase.{instance._meta.model_name}.create", object_instance=instance, after=audit_snapshot(instance), company_id=supplier.company_id, request=self.request)

    def perform_update(self, serializer):
        supplier = self.get_supplier(self.manage_permission)
        if serializer.instance.supplier_id != supplier.id:
            raise NotFound()
        before = audit_snapshot(serializer.instance)
        with transaction.atomic():
            instance = serializer.save()
            record_audit_event(organization=self.request.user.organization, actor=self.request.user, action=f"purchase.{instance._meta.model_name}.update", object_instance=instance, before=before, after=audit_snapshot(instance), company_id=supplier.company_id, request=self.request)


class SupplierContactListCreateView(SupplierChildMixin, generics.ListCreateAPIView):
    queryset = SupplierContact.objects.none()
    serializer_class = SupplierContactSerializer
    permission_classes = [IsAuthenticated]
    ordering = ("-is_primary", "name")

    def get_queryset(self):
        return SupplierContact.objects.filter(supplier=self.get_supplier())


class SupplierContactDetailView(SupplierChildMixin, generics.RetrieveUpdateAPIView):
    queryset = SupplierContact.objects.none()
    serializer_class = SupplierContactSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "contact_id"

    def get_queryset(self):
        permission = "purchase.supplier.view" if self.request.method == "GET" else "purchase.supplier.manage"
        return SupplierContact.objects.filter(supplier=self.get_supplier(permission))


class SupplierAddressListCreateView(SupplierChildMixin, generics.ListCreateAPIView):
    queryset = SupplierAddress.objects.none()
    serializer_class = SupplierAddressSerializer
    permission_classes = [IsAuthenticated]
    ordering = ("-is_primary", "label", "city")

    def get_queryset(self):
        return SupplierAddress.objects.filter(supplier=self.get_supplier())


class SupplierAddressDetailView(SupplierChildMixin, generics.RetrieveUpdateAPIView):
    queryset = SupplierAddress.objects.none()
    serializer_class = SupplierAddressSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "address_id"

    def get_queryset(self):
        permission = "purchase.supplier.view" if self.request.method == "GET" else "purchase.supplier.manage"
        return SupplierAddress.objects.filter(supplier=self.get_supplier(permission))


class SupplierProductListCreateView(SupplierChildMixin, generics.ListCreateAPIView):
    queryset = SupplierProduct.objects.none()
    serializer_class = SupplierProductSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("product_id", "product_variant_id", "unit_id", "currency_id", "is_preferred")
    search_fields = ("supplier_sku", "product__code", "product__name")
    ordering_fields = ("lead_time_days", "last_unit_price", "created_at")
    ordering = ("product__name",)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["supplier"] = self.get_supplier("purchase.supplier.manage" if self.request.method == "POST" else "purchase.supplier.view")
        return context

    def get_queryset(self):
        return SupplierProduct.objects.filter(supplier=self.get_supplier()).select_related("supplier", "product", "product_variant", "unit", "currency")


class SupplierProductDetailView(SupplierChildMixin, generics.RetrieveUpdateAPIView):
    queryset = SupplierProduct.objects.none()
    serializer_class = SupplierProductSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "supplier_product_id"

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["supplier"] = self.get_supplier("purchase.supplier.view" if self.request.method == "GET" else "purchase.supplier.manage")
        return context

    def get_queryset(self):
        permission = "purchase.supplier.view" if self.request.method == "GET" else "purchase.supplier.manage"
        return SupplierProduct.objects.filter(supplier=self.get_supplier(permission)).select_related("supplier", "product", "product_variant", "unit", "currency")
