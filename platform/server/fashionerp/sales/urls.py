from django.urls import path
from .views import OrderListCreateView,QuotationListCreateView,OrderActionView,QuotationActionView
urlpatterns=[path("quotations/",QuotationListCreateView.as_view()),path("quotations/<uuid:quotation_id>/actions/<str:action>/",QuotationActionView.as_view()),path("orders/",OrderListCreateView.as_view()),path("orders/<uuid:order_id>/actions/<str:action>/",OrderActionView.as_view())]
