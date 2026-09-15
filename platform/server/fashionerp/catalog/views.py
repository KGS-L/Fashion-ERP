from django.db import models, transaction
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated

from fashionerp.audit.services import audit_snapshot, record_audit_event
from fashionerp.authorization.services import authorized_company_ids, has_permission

from .models import Product, ProductAttribute, ProductVariant
from .serializers import ProductAttributeSerializer, ProductSerializer, ProductVariantSerializer


def scoped_products(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return Product.objects.filter(organization_id=user.organization_id, company__isnull=True)
    return Product.objects.filter(organization_id=user.organization_id).filter(
        models.Q(company__isnull=True) | models.Q(company_id__in=company_ids)
    ).select_related("company", "unit").prefetch_related("variants", "variants__attribute_values")


class ProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.none()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "product_type", "is_active")
    search_fields = ("code", "name", "variants__sku", "variants__barcode")
    ordering_fields = ("name", "code", "product_type", "created_at", "updated_at")
    ordering = ("name",)

    def get_queryset(self):
        return scoped_products(self.request.user, "fashion.product.view")

    def perform_create(self, serializer):
        company = serializer.validated_data.get("company")
        if not has_permission(self.request.user, "fashion.product.manage", company=company):
            raise PermissionDenied("You cannot manage products in this scope.")
        with transaction.atomic():
            product = serializer.save(organization=self.request.user.organization)
            record_audit_event(organization=self.request.user.organization, actor=self.request.user, action="fashion.product.create", object_instance=product, after=audit_snapshot(product), request=self.request)


class ProductDetailView(generics.RetrieveUpdateAPIView):
    queryset = Product.objects.none()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "product_id"

    def get_queryset(self):
        permission = "fashion.product.view" if self.request.method == "GET" else "fashion.product.manage"
        return scoped_products(self.request.user, permission)

    def perform_update(self, serializer):
        before = audit_snapshot(serializer.instance)
        product = serializer.save()
        record_audit_event(organization=self.request.user.organization, actor=self.request.user, action="fashion.product.update", object_instance=product, before=before, after=audit_snapshot(product), request=self.request)


class ProductAttributeListCreateView(generics.ListCreateAPIView):
    queryset = ProductAttribute.objects.none()
    serializer_class = ProductAttributeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not authorized_company_ids(self.request.user, "fashion.product.view"):
            return ProductAttribute.objects.none()
        return ProductAttribute.objects.filter(organization_id=self.request.user.organization_id).prefetch_related("values")

    def perform_create(self, serializer):
        if not authorized_company_ids(self.request.user, "fashion.product.manage"):
            raise PermissionDenied("You cannot manage product attributes.")
        serializer.save(organization=self.request.user.organization)


class ProductVariantCreateView(generics.CreateAPIView):
    queryset = ProductVariant.objects.none()
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["product"] = self.get_product()
        return context

    def get_product(self):
        return scoped_products(self.request.user, "fashion.product.manage").get(id=self.kwargs["product_id"])

    def perform_create(self, serializer):
        product = self.get_product()
        if not has_permission(self.request.user, "fashion.product.manage", company=product.company):
            raise PermissionDenied("You cannot manage variants for this product.")
        serializer.save(product=product)
