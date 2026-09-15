from django.urls import path

from .views import (
    EmployeeAssignmentDetailView,
    EmployeeAssignmentListView,
    EmployeeContractDetailView,
    EmployeeContractListView,
    EmployeeDetailView,
    EmployeeListView,
    EmployeeSkillDetailView,
    EmployeeSkillListView,
    SkillDetailView,
    SkillListView,
)


app_name = "employees"

urlpatterns = [
    path("", EmployeeListView.as_view(), name="list"),
    path("skills/", SkillListView.as_view(), name="skill-list"),
    path("skills/<uuid:skill_id>/", SkillDetailView.as_view(), name="skill-detail"),
    path("employee-skills/", EmployeeSkillListView.as_view(), name="employee-skill-list"),
    path(
        "employee-skills/<uuid:employee_skill_id>/",
        EmployeeSkillDetailView.as_view(),
        name="employee-skill-detail",
    ),
    path("contracts/", EmployeeContractListView.as_view(), name="contract-list"),
    path(
        "contracts/<uuid:contract_id>/",
        EmployeeContractDetailView.as_view(),
        name="contract-detail",
    ),
    path("assignments/", EmployeeAssignmentListView.as_view(), name="assignment-list"),
    path(
        "assignments/<uuid:assignment_id>/",
        EmployeeAssignmentDetailView.as_view(),
        name="assignment-detail",
    ),
    path("<uuid:employee_id>/", EmployeeDetailView.as_view(), name="detail"),
]
