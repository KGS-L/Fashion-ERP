from django.urls import path

from .views import (
    CollectionListCreateView, FashionModelListCreateView, FashionModelMaterialRequirementListCreateView, ProductAttributeListCreateView,
    ProductDetailView, ProductListCreateView, ProductVariantCreateView, SeasonListCreateView,
)

app_name = "catalog"

urlpatterns = [
    path("", ProductListCreateView.as_view(), name="list-create"),
    path("attributes/", ProductAttributeListCreateView.as_view(), name="attributes"),
    path("seasons/", SeasonListCreateView.as_view(), name="seasons"),
    path("collections/", CollectionListCreateView.as_view(), name="collections"),
    path("fashion-models/", FashionModelListCreateView.as_view(), name="fashion-models"),
    path("fashion-models/<uuid:fashion_model_id>/material-requirements/", FashionModelMaterialRequirementListCreateView.as_view(), name="fashion-model-material-requirements"),
    path("<uuid:product_id>/", ProductDetailView.as_view(), name="detail"),
    path("<uuid:product_id>/variants/", ProductVariantCreateView.as_view(), name="variant-create"),
]
