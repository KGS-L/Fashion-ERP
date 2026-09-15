from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated

from ivadoo.authorization.services import (
    authorized_company_ids,
    authorized_establishment_ids,
    has_permission,
)

from .models import (
    AttendanceRecord,
    EmployeeSchedule,
    EmployeeTask,
    EmployeeTaskTransition,
    EmployeeTimeEntry,
)
from .views import record_change
from .work_serializers import (
    AttendanceRecordSerializer,
    EmployeeScheduleSerializer,
    EmployeeTaskSerializer,
    EmployeeTimeEntrySerializer,
)


WORK_VIEW = "enterprise.employee.work.view"
WORK_MANAGE = "enterprise.employee.work.manage"

TASK_TRANSITIONS = {
    EmployeeTask.Status.PENDING: {
        EmployeeTask.Status.IN_PROGRESS,
        EmployeeTask.Status.CANCELLED,
    },
    EmployeeTask.Status.IN_PROGRESS: {
        EmployeeTask.Status.BLOCKED,
        EmployeeTask.Status.DONE,
        EmployeeTask.Status.CANCELLED,
    },
    EmployeeTask.Status.BLOCKED: {
        EmployeeTask.Status.IN_PROGRESS,
        EmployeeTask.Status.CANCELLED,
    },
    EmployeeTask.Status.DONE: set(),
    EmployeeTask.Status.CANCELLED: set(),
}


def scoped_work_records(queryset, user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    establishment_ids = authorized_establishment_ids(user, permission_code)
    if not company_ids and not establishment_ids:
        return queryset.none()
    return queryset.filter(employee__organization_id=user.organization_id).filter(
        Q(company_id__in=company_ids)
        | Q(establishment_id__in=establishment_ids)
        | Q(workshop_id__in=establishment_ids)
    )


def assert_work_scope(user, *, company, establishment=None, workshop=None):
    target_site = workshop or establishment
    if not has_permission(
        user,
        WORK_MANAGE,
        company=company,
        establishment=target_site,
    ):
        raise PermissionDenied("You cannot manage employee work records in this scope.")


class EmployeeScheduleListView(generics.ListCreateAPIView):
    queryset = EmployeeSchedule.objects.none()
    serializer_class = EmployeeScheduleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "employee_id",
        "company_id",
        "establishment_id",
        "workshop_id",
        "status",
    )
    search_fields = ("label", "notes", "employee__display_name", "employee__code")
    ordering_fields = ("starts_at", "ends_at", "created_at", "updated_at")
    ordering = ("starts_at",)

    def get_queryset(self):
        return scoped_work_records(
            EmployeeSchedule.objects.select_related(
                "employee", "company", "establishment", "workshop", "created_by"
            ),
            self.request.user,
            WORK_VIEW,
        )

    def perform_create(self, serializer):
        assert_work_scope(
            self.request.user,
            company=serializer.validated_data["company"],
            establishment=serializer.validated_data.get("establishment"),
            workshop=serializer.validated_data.get("workshop"),
        )
        with transaction.atomic():
            schedule = serializer.save(created_by=self.request.user)
            record_change(
                request=self.request,
                action="enterprise.employee_schedule.create",
                instance=schedule,
            )


class EmployeeScheduleDetailView(generics.RetrieveUpdateAPIView):
    queryset = EmployeeSchedule.objects.none()
    serializer_class = EmployeeScheduleSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "schedule_id"

    def get_queryset(self):
        permission = WORK_VIEW if self.request.method == "GET" else WORK_MANAGE
        return scoped_work_records(EmployeeSchedule.objects.all(), self.request.user, permission)

    def perform_update(self, serializer):
        assert_work_scope(
            self.request.user,
            company=serializer.validated_data.get("company", serializer.instance.company),
            establishment=serializer.validated_data.get(
                "establishment", serializer.instance.establishment
            ),
            workshop=serializer.validated_data.get("workshop", serializer.instance.workshop),
        )
        with transaction.atomic():
            from ivadoo.audit.services import audit_snapshot

            before = audit_snapshot(serializer.instance)
            schedule = serializer.save()
            record_change(
                request=self.request,
                action="enterprise.employee_schedule.update",
                instance=schedule,
                before=before,
            )


class AttendanceRecordListView(generics.ListCreateAPIView):
    queryset = AttendanceRecord.objects.none()
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "employee_id",
        "company_id",
        "establishment_id",
        "workshop_id",
        "attendance_date",
        "status",
    )
    search_fields = ("employee__display_name", "employee__code", "notes")
    ordering_fields = ("attendance_date", "check_in_at", "check_out_at", "created_at")
    ordering = ("-attendance_date",)

    def get_queryset(self):
        return scoped_work_records(
            AttendanceRecord.objects.select_related(
                "employee",
                "schedule",
                "company",
                "establishment",
                "workshop",
                "recorded_by",
            ),
            self.request.user,
            WORK_VIEW,
        )

    def perform_create(self, serializer):
        assert_work_scope(
            self.request.user,
            company=serializer.validated_data["company"],
            establishment=serializer.validated_data.get("establishment"),
            workshop=serializer.validated_data.get("workshop"),
        )
        with transaction.atomic():
            attendance = serializer.save(recorded_by=self.request.user)
            record_change(
                request=self.request,
                action="enterprise.employee_attendance.create",
                instance=attendance,
            )


class AttendanceRecordDetailView(generics.RetrieveUpdateAPIView):
    queryset = AttendanceRecord.objects.none()
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "attendance_id"

    def get_queryset(self):
        permission = WORK_VIEW if self.request.method == "GET" else WORK_MANAGE
        return scoped_work_records(AttendanceRecord.objects.all(), self.request.user, permission)

    def perform_update(self, serializer):
        assert_work_scope(
            self.request.user,
            company=serializer.validated_data.get("company", serializer.instance.company),
            establishment=serializer.validated_data.get(
                "establishment", serializer.instance.establishment
            ),
            workshop=serializer.validated_data.get("workshop", serializer.instance.workshop),
        )
        with transaction.atomic():
            from ivadoo.audit.services import audit_snapshot

            before = audit_snapshot(serializer.instance)
            attendance = serializer.save()
            record_change(
                request=self.request,
                action="enterprise.employee_attendance.update",
                instance=attendance,
                before=before,
            )


class EmployeeTaskListView(generics.ListCreateAPIView):
    queryset = EmployeeTask.objects.none()
    serializer_class = EmployeeTaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "employee_id",
        "company_id",
        "establishment_id",
        "workshop_id",
        "order_id",
        "manufacturing_operation_id",
        "status",
        "priority",
    )
    search_fields = ("title", "description", "employee__display_name", "employee__code")
    ordering_fields = ("priority", "planned_start", "due_at", "created_at", "updated_at")
    ordering = ("due_at", "created_at")

    def get_queryset(self):
        return scoped_work_records(
            EmployeeTask.objects.select_related(
                "employee",
                "company",
                "establishment",
                "workshop",
                "order",
                "manufacturing_operation",
                "created_by",
            ),
            self.request.user,
            WORK_VIEW,
        )

    def perform_create(self, serializer):
        assert_work_scope(
            self.request.user,
            company=serializer.validated_data["company"],
            establishment=serializer.validated_data.get("establishment"),
            workshop=serializer.validated_data.get("workshop"),
        )
        with transaction.atomic():
            task = serializer.save(created_by=self.request.user)
            EmployeeTaskTransition.objects.create(
                task=task,
                from_status="",
                to_status=task.status,
                actor=self.request.user,
                note="Task created",
            )
            record_change(
                request=self.request,
                action="enterprise.employee_task.create",
                instance=task,
            )


class EmployeeTaskDetailView(generics.RetrieveUpdateAPIView):
    queryset = EmployeeTask.objects.none()
    serializer_class = EmployeeTaskSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "task_id"

    def get_queryset(self):
        permission = WORK_VIEW if self.request.method == "GET" else WORK_MANAGE
        return scoped_work_records(EmployeeTask.objects.all(), self.request.user, permission)

    def perform_update(self, serializer):
        assert_work_scope(
            self.request.user,
            company=serializer.validated_data.get("company", serializer.instance.company),
            establishment=serializer.validated_data.get(
                "establishment", serializer.instance.establishment
            ),
            workshop=serializer.validated_data.get("workshop", serializer.instance.workshop),
        )
        old_status = serializer.instance.status
        new_status = serializer.validated_data.get("status", old_status)
        if new_status != old_status and new_status not in TASK_TRANSITIONS[old_status]:
            raise ValidationError(
                {"status": f"Transition {old_status} -> {new_status} is not allowed."}
            )

        if new_status == EmployeeTask.Status.IN_PROGRESS and not (
            serializer.validated_data.get("started_at") or serializer.instance.started_at
        ):
            serializer.validated_data["started_at"] = timezone.now()
        if new_status == EmployeeTask.Status.DONE and not (
            serializer.validated_data.get("completed_at") or serializer.instance.completed_at
        ):
            serializer.validated_data["completed_at"] = timezone.now()

        with transaction.atomic():
            from ivadoo.audit.services import audit_snapshot

            before = audit_snapshot(serializer.instance)
            task = serializer.save()
            if new_status != old_status:
                EmployeeTaskTransition.objects.create(
                    task=task,
                    from_status=old_status,
                    to_status=new_status,
                    actor=self.request.user,
                )
            record_change(
                request=self.request,
                action="enterprise.employee_task.update",
                instance=task,
                before=before,
            )


class EmployeeTimeEntryListView(generics.ListCreateAPIView):
    queryset = EmployeeTimeEntry.objects.none()
    serializer_class = EmployeeTimeEntrySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "employee_id",
        "task_id",
        "company_id",
        "establishment_id",
        "workshop_id",
        "source",
    )
    search_fields = ("employee__display_name", "employee__code", "notes", "task__title")
    ordering_fields = ("started_at", "ended_at", "duration_minutes", "created_at")
    ordering = ("-started_at",)

    def get_queryset(self):
        return scoped_work_records(
            EmployeeTimeEntry.objects.select_related(
                "employee",
                "task",
                "company",
                "establishment",
                "workshop",
                "recorded_by",
            ),
            self.request.user,
            WORK_VIEW,
        )

    def perform_create(self, serializer):
        assert_work_scope(
            self.request.user,
            company=serializer.validated_data["company"],
            establishment=serializer.validated_data.get("establishment"),
            workshop=serializer.validated_data.get("workshop"),
        )
        with transaction.atomic():
            entry = serializer.save(recorded_by=self.request.user)
            record_change(
                request=self.request,
                action="enterprise.employee_time.create",
                instance=entry,
            )


class EmployeeTimeEntryDetailView(generics.RetrieveUpdateAPIView):
    queryset = EmployeeTimeEntry.objects.none()
    serializer_class = EmployeeTimeEntrySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "time_entry_id"

    def get_queryset(self):
        permission = WORK_VIEW if self.request.method == "GET" else WORK_MANAGE
        return scoped_work_records(EmployeeTimeEntry.objects.all(), self.request.user, permission)

    def perform_update(self, serializer):
        assert_work_scope(
            self.request.user,
            company=serializer.validated_data.get("company", serializer.instance.company),
            establishment=serializer.validated_data.get(
                "establishment", serializer.instance.establishment
            ),
            workshop=serializer.validated_data.get("workshop", serializer.instance.workshop),
        )
        with transaction.atomic():
            from ivadoo.audit.services import audit_snapshot

            before = audit_snapshot(serializer.instance)
            entry = serializer.save()
            record_change(
                request=self.request,
                action="enterprise.employee_time.update",
                instance=entry,
                before=before,
            )
