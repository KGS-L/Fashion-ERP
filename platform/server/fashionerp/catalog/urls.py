from django.urls import path

from .views import ProductAttributeListCreateView, ProductDetailView, ProductListCreateView, ProductVariantCreateView

app_name = "catalog"

urlpatterns = [
    path("", ProductListCreateView.as_view(), name="list-create"),
    path("attributes/", ProductAttributeListCreateView.as_view(), name="attributes"),
    path("<uuid:product_id>/", ProductDetailView.as_view(), name="detail"),
    path("<uuid:product_id>/variants/", ProductVariantCreateView.as_view(), name="variant-create"),
]
