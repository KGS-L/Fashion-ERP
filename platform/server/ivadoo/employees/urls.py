from django.urls import path

from .performance_views import (
    CommissionCalculateView,
    CommissionCalculationListView,
    CommissionRuleDetailView,
    CommissionRuleListView,
    ProductivityGenerateView,
    ProductivitySnapshotListView,
)
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
from .work_views import (
    AttendanceRecordDetailView,
    AttendanceRecordListView,
    EmployeeScheduleDetailView,
    EmployeeScheduleListView,
    EmployeeTaskDetailView,
    EmployeeTaskListView,
    EmployeeTimeEntryDetailView,
    EmployeeTimeEntryListView,
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
    path("schedules/", EmployeeScheduleListView.as_view(), name="schedule-list"),
    path(
        "schedules/<uuid:schedule_id>/",
        EmployeeScheduleDetailView.as_view(),
        name="schedule-detail",
    ),
    path("attendance/", AttendanceRecordListView.as_view(), name="attendance-list"),
    path(
        "attendance/<uuid:attendance_id>/",
        AttendanceRecordDetailView.as_view(),
        name="attendance-detail",
    ),
    path("tasks/", EmployeeTaskListView.as_view(), name="task-list"),
    path("tasks/<uuid:task_id>/", EmployeeTaskDetailView.as_view(), name="task-detail"),
    path("time-entries/", EmployeeTimeEntryListView.as_view(), name="time-entry-list"),
    path(
        "time-entries/<uuid:time_entry_id>/",
        EmployeeTimeEntryDetailView.as_view(),
        name="time-entry-detail",
    ),
    path(
        "productivity/",
        ProductivitySnapshotListView.as_view(),
        name="productivity-list",
    ),
    path(
        "productivity/actions/generate/",
        ProductivityGenerateView.as_view(),
        name="productivity-generate",
    ),
    path(
        "commission-rules/",
        CommissionRuleListView.as_view(),
        name="commission-rule-list",
    ),
    path(
        "commission-rules/<uuid:rule_id>/",
        CommissionRuleDetailView.as_view(),
        name="commission-rule-detail",
    ),
    path(
        "commissions/",
        CommissionCalculationListView.as_view(),
        name="commission-list",
    ),
    path(
        "commissions/actions/calculate/",
        CommissionCalculateView.as_view(),
        name="commission-calculate",
    ),
    path("<uuid:employee_id>/", EmployeeDetailView.as_view(), name="detail"),
]
