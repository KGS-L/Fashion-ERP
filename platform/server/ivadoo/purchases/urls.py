from django.urls import path

from .procurement_views import (
    PurchaseOrderActionView,
    PurchaseOrderDetailView,
    PurchaseOrderListCreateView,
    PurchaseRequestActionView,
    PurchaseRequestDetailView,
    PurchaseRequestListCreateView,
    RFQActionView,
    RFQComparisonView,
    RFQDetailView,
    RFQListCreateView,
    SupplierQuotationListCreateView,
    SupplierQuotationSelectView,
)
from .views import (
    SupplierAddressDetailView,
    SupplierAddressListCreateView,
    SupplierContactDetailView,
    SupplierContactListCreateView,
    SupplierDetailView,
    SupplierListCreateView,
    SupplierProductDetailView,
    SupplierProductListCreateView,
)


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
    path("requests/", PurchaseRequestListCreateView.as_view(), name="request-list"),
    path("requests/<uuid:request_id>/", PurchaseRequestDetailView.as_view(), name="request-detail"),
    path("requests/<uuid:request_id>/actions/", PurchaseRequestActionView.as_view(), name="request-action"),
    path("rfqs/", RFQListCreateView.as_view(), name="rfq-list"),
    path("rfqs/<uuid:rfq_id>/", RFQDetailView.as_view(), name="rfq-detail"),
    path("rfqs/<uuid:rfq_id>/actions/", RFQActionView.as_view(), name="rfq-action"),
    path("rfqs/<uuid:rfq_id>/quotes/", SupplierQuotationListCreateView.as_view(), name="rfq-quote-list"),
    path("rfqs/<uuid:rfq_id>/quotes/<uuid:quotation_id>/select/", SupplierQuotationSelectView.as_view(), name="rfq-quote-select"),
    path("rfqs/<uuid:rfq_id>/comparison/", RFQComparisonView.as_view(), name="rfq-comparison"),
    path("orders/", PurchaseOrderListCreateView.as_view(), name="order-list"),
    path("orders/<uuid:purchase_order_id>/", PurchaseOrderDetailView.as_view(), name="order-detail"),
    path("orders/<uuid:purchase_order_id>/actions/", PurchaseOrderActionView.as_view(), name="order-action"),
]
