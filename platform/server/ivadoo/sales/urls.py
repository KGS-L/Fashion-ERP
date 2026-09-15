from django.urls import path

from .fitting_views import (
    AlterationActionView,
    AlterationListCreateView,
    CustomerValidationListCreateView,
    FittingActionView,
    FittingSessionDetailView,
    FittingSessionListCreateView,
    OrderDeliveryReadinessView,
)
from .views import OrderActionView, OrderListCreateView, QuotationActionView, QuotationListCreateView


urlpatterns = [
    path("quotations/", QuotationListCreateView.as_view()),
    path("quotations/<uuid:quotation_id>/actions/<str:action>/", QuotationActionView.as_view()),
    path("orders/", OrderListCreateView.as_view()),
    path("orders/<uuid:order_id>/actions/<str:action>/", OrderActionView.as_view()),
    path("orders/<uuid:order_id>/delivery-readiness/", OrderDeliveryReadinessView.as_view()),
    path("fittings/", FittingSessionListCreateView.as_view()),
    path("fittings/<uuid:fitting_id>/", FittingSessionDetailView.as_view()),
    path("fittings/<uuid:fitting_id>/actions/<str:action>/", FittingActionView.as_view()),
    path("alterations/", AlterationListCreateView.as_view()),
    path("alterations/<uuid:alteration_id>/actions/<str:action>/", AlterationActionView.as_view()),
    path("customer-validations/", CustomerValidationListCreateView.as_view()),
]
