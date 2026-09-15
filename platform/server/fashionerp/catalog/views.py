from django.db import models, transaction
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated

from fashionerp.audit.services import audit_snapshot, record_audit_event
from fashionerp.authorization.services import authorized_company_ids, has_permission

from .models import Collection, FashionModel, FashionModelMaterialRequirement, Product, ProductAttribute, ProductVariant, Season
from .serializers import (
    CollectionSerializer, FashionModelMaterialRequirementSerializer, FashionModelSerializer, ProductAttributeSerializer,
    ProductSerializer, ProductVariantSerializer, SeasonSerializer,
)


def scoped_products(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return Product.objects.none()
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


def has_catalog_scope(user, permission_code):
    return bool(authorized_company_ids(user, permission_code))


class SeasonListCreateView(generics.ListCreateAPIView):
    queryset = Season.objects.none()
    serializer_class = SeasonSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("year", "is_active")
    search_fields = ("code", "name")
    ordering_fields = ("year", "name")
    ordering = ("-year", "name")

    def get_queryset(self):
        if not has_catalog_scope(self.request.user, "fashion.product.view"):
            return Season.objects.none()
        return Season.objects.filter(organization_id=self.request.user.organization_id)

    def perform_create(self, serializer):
        if not has_catalog_scope(self.request.user, "fashion.product.manage"):
            raise PermissionDenied("You cannot manage fashion seasons.")
        serializer.save(organization=self.request.user.organization)


class CollectionListCreateView(generics.ListCreateAPIView):
    queryset = Collection.objects.none()
    serializer_class = CollectionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "season_id", "is_active")
    search_fields = ("code", "name")
    ordering_fields = ("name", "created_at", "updated_at")
    ordering = ("name",)

    def get_queryset(self):
        if not has_catalog_scope(self.request.user, "fashion.product.view"):
            return Collection.objects.none()
        company_ids = authorized_company_ids(self.request.user, "fashion.product.view")
        return Collection.objects.filter(organization_id=self.request.user.organization_id).filter(
            models.Q(company__isnull=True) | models.Q(company_id__in=company_ids)
        ).select_related("company", "season")

    def perform_create(self, serializer):
        company = serializer.validated_data.get("company")
        if not has_permission(self.request.user, "fashion.product.manage", company=company):
            raise PermissionDenied("You cannot manage collections in this scope.")
        serializer.save(organization=self.request.user.organization)


class FashionModelListCreateView(generics.ListCreateAPIView):
    queryset = FashionModel.objects.none()
    serializer_class = FashionModelSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("company_id", "collection_id", "is_active")
    search_fields = ("code", "name", "variants__code", "variants__color", "variants__size")
    ordering_fields = ("name", "created_at", "updated_at")
    ordering = ("name",)

    def get_queryset(self):
        company_ids = authorized_company_ids(self.request.user, "fashion.product.view")
        if not company_ids:
            return FashionModel.objects.none()
        return FashionModel.objects.filter(organization_id=self.request.user.organization_id).filter(
            models.Q(company__isnull=True) | models.Q(company_id__in=company_ids)
        ).select_related("company", "collection", "collection__season").prefetch_related("variants")

    def perform_create(self, serializer):
        company = serializer.validated_data.get("company")
        if not has_permission(self.request.user, "fashion.product.manage", company=company):
            raise PermissionDenied("You cannot manage fashion models in this scope.")
        with transaction.atomic():
            model = serializer.save(organization=self.request.user.organization)
            record_audit_event(organization=self.request.user.organization, actor=self.request.user, action="fashion.model.create", object_instance=model, after=audit_snapshot(model), request=self.request)


class FashionModelMaterialRequirementListCreateView(generics.ListCreateAPIView):
    queryset = FashionModelMaterialRequirement.objects.none()
    serializer_class = FashionModelMaterialRequirementSerializer
    permission_classes = [IsAuthenticated]

    def get_fashion_model(self, permission_code):
        company_ids = authorized_company_ids(self.request.user, permission_code)
        return FashionModel.objects.filter(
            organization_id=self.request.user.organization_id
        ).filter(
            models.Q(company__isnull=True) | models.Q(company_id__in=company_ids)
        ).get(id=self.kwargs["fashion_model_id"])

    def get_queryset(self):
        fashion_model = self.get_fashion_model("fashion.product.view")
        return FashionModelMaterialRequirement.objects.filter(
            fashion_model=fashion_model
        ).select_related("model_variant", "product", "product_variant", "unit")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["fashion_model"] = self.get_fashion_model(
            "fashion.product.manage" if self.request.method == "POST" else "fashion.product.view"
        )
        return context

    def perform_create(self, serializer):
        fashion_model = self.get_fashion_model("fashion.product.manage")
        if not has_permission(self.request.user, "fashion.product.manage", company=fashion_model.company):
            raise PermissionDenied("You cannot manage material requirements for this model.")
        requirement = serializer.save(fashion_model=fashion_model)
        record_audit_event(
            organization=self.request.user.organization, actor=self.request.user,
            action="fashion.model.material_requirement.create",
            object_instance=requirement, after=audit_snapshot(requirement), request=self.request,
        )
