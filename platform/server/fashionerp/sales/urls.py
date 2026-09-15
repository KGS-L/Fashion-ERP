from django.urls import path
from .views import OrderListCreateView,QuotationListCreateView,order_action,quotation_action
urlpatterns=[path("quotations/",QuotationListCreateView.as_view()),path("quotations/<uuid:quotation_id>/actions/<str:action>/",quotation_action),path("orders/",OrderListCreateView.as_view()),path("orders/<uuid:order_id>/actions/<str:action>/",order_action)]
