from django.urls import path

from .views import ApprovalRuleDetailView, ApprovalRuleListCreateView, StockApprovalDecisionView, StockApprovalListCreateView


urlpatterns = [
    path("approval-rules/", ApprovalRuleListCreateView.as_view(), name="approval-rule-list"),
    path("approval-rules/<uuid:rule_id>/", ApprovalRuleDetailView.as_view(), name="approval-rule-detail"),
    path("stock-movement-approvals/", StockApprovalListCreateView.as_view(), name="stock-approval-list"),
    path("stock-movement-approvals/<uuid:approval_id>/decision/", StockApprovalDecisionView.as_view(), name="stock-approval-decision"),
]
