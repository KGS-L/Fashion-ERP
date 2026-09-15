from django.urls import path

from .views import SupplierAddressDetailView, SupplierAddressListCreateView, SupplierContactDetailView, SupplierContactListCreateView, SupplierDetailView, SupplierListCreateView, SupplierProductDetailView, SupplierProductListCreateView


app_name = "purchases"

urlpatterns = [
    path("suppliers/", SupplierListCreateView.as_view(), name="supplier-list"),
    path("suppliers/<uuid:supplier_id>/", SupplierDetailView.as_view(), name="supplier-detail"),
    path("suppliers/<uuid:supplier_id>/contacts/", SupplierContactListCreateView.as_view(), name="supplier-contact-list"),
    path("suppliers/<uuid:supplier_id>/contacts/<uuid:contact_id>/", SupplierContactDetailView.as_view(), name="supplier-contact-detail"),
    path("suppliers/<uuid:supplier_id>/addresses/", SupplierAddressListCreateView.as_view(), name="supplier-address-list"),
    path("suppliers/<uuid:supplier_id>/addresses/<uuid:address_id>/", SupplierAddressDetailView.as_view(), name="supplier-address-detail"),
    path("suppliers/<uuid:supplier_id>/products/", SupplierProductListCreateView.as_view(), name="supplier-product-list"),
    path("suppliers/<uuid:supplier_id>/products/<uuid:supplier_product_id>/", SupplierProductDetailView.as_view(), name="supplier-product-detail"),
]
