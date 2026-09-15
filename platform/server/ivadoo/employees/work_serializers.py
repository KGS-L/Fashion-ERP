from rest_framework import serializers

from ivadoo.manufacturing.models import ManufacturingOperation
from ivadoo.organizations.models import Company, Establishment
from ivadoo.sales.models import Order

from .models import (
    AttendanceRecord,
    Employee,
    EmployeeSchedule,
    EmployeeTask,
    EmployeeTimeEntry,
)


def validate_scope(attrs, instance, request):
    employee = attrs.get("employee", getattr(instance, "employee", None))
    company = attrs.get("company", getattr(instance, "company", None))
    establishment = attrs.get("establishment", getattr(instance, "establishment", None))
    workshop = attrs.get("workshop", getattr(instance, "workshop", None))

    if request and employee and employee.organization_id != request.user.organization_id:
        raise serializers.ValidationError(
            {"employee_id": "Employee is outside the local organization."}
        )
    if request and company and company.organization_id != request.user.organization_id:
        raise serializers.ValidationError(
            {"company_id": "Company is outside the local organization."}
        )
    if employee and company and employee.organization_id != company.organization_id:
        raise serializers.ValidationError(
            {"company_id": "Company must belong to the employee organization."}
        )
    if establishment and company and establishment.company_id != company.id:
        raise serializers.ValidationError(
            {"establishment_id": "Establishment must belong to the selected company."}
        )
    if workshop:
        if company and workshop.company_id != company.id:
            raise serializers.ValidationError(
                {"workshop_id": "Workshop must belong to the selected company."}
            )
        if workshop.site_type not in {"workshop", "mixed"}:
            raise serializers.ValidationError(
                {"workshop_id": "Workshop must use the workshop or mixed establishment type."}
            )
    return employee, company, establishment, workshop


class ScopedWorkSerializer(serializers.ModelSerializer):
    employee_id = serializers.PrimaryKeyRelatedField(
        source="employee", queryset=Employee.objects.all()
    )
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )
    establishment_id = serializers.PrimaryKeyRelatedField(
        source="establishment",
        queryset=Establishment.objects.all(),
        allow_null=True,
        required=False,
    )
    workshop_id = serializers.PrimaryKeyRelatedField(
        source="workshop",
        queryset=Establishment.objects.filter(site_type__in=("workshop", "mixed")),
        allow_null=True,
        required=False,
    )

    class Meta:
        abstract = True


class EmployeeScheduleSerializer(ScopedWorkSerializer):
    class Meta:
        model = EmployeeSchedule
        fields = (
            "id",
            "employee_id",
            "company_id",
            "establishment_id",
            "workshop_id",
            "label",
            "starts_at",
            "ends_at",
            "status",
            "notes",
            "created_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by_id", "created_at", "updated_at")

    def validate(self, attrs):
        validate_scope(attrs, self.instance, self.context.get("request"))
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError(
                {"ends_at": "Schedule end must be after its start."}
            )
        return attrs


class AttendanceRecordSerializer(ScopedWorkSerializer):
    schedule_id = serializers.PrimaryKeyRelatedField(
        source="schedule",
        queryset=EmployeeSchedule.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = AttendanceRecord
        fields = (
            "id",
            "employee_id",
            "schedule_id",
            "company_id",
            "establishment_id",
            "workshop_id",
            "attendance_date",
            "status",
            "check_in_at",
            "check_out_at",
            "notes",
            "recorded_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "recorded_by_id", "created_at", "updated_at")

    def validate(self, attrs):
        employee, company, _, _ = validate_scope(
            attrs, self.instance, self.context.get("request")
        )
        schedule = attrs.get("schedule", getattr(self.instance, "schedule", None))
        check_in_at = attrs.get("check_in_at", getattr(self.instance, "check_in_at", None))
        check_out_at = attrs.get(
            "check_out_at", getattr(self.instance, "check_out_at", None)
        )
        if schedule:
            if employee and schedule.employee_id != employee.id:
                raise serializers.ValidationError(
                    {"schedule_id": "Schedule must belong to the selected employee."}
                )
            if company and schedule.company_id != company.id:
                raise serializers.ValidationError(
                    {"schedule_id": "Schedule must belong to the selected company."}
                )
        if check_in_at and check_out_at and check_out_at < check_in_at:
            raise serializers.ValidationError(
                {"check_out_at": "Check-out cannot precede check-in."}
            )
        return attrs


class EmployeeTaskSerializer(ScopedWorkSerializer):
    order_id = serializers.PrimaryKeyRelatedField(
        source="order",
        queryset=Order.objects.all(),
        allow_null=True,
        required=False,
    )
    manufacturing_operation_id = serializers.PrimaryKeyRelatedField(
        source="manufacturing_operation",
        queryset=ManufacturingOperation.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = EmployeeTask
        fields = (
            "id",
            "employee_id",
            "company_id",
            "establishment_id",
            "workshop_id",
            "order_id",
            "manufacturing_operation_id",
            "title",
            "description",
            "status",
            "priority",
            "planned_start",
            "due_at",
            "started_at",
            "completed_at",
            "created_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by_id", "created_at", "updated_at")

    def validate(self, attrs):
        employee, company, _, _ = validate_scope(
            attrs, self.instance, self.context.get("request")
        )
        order = attrs.get("order", getattr(self.instance, "order", None))
        operation = attrs.get(
            "manufacturing_operation",
            getattr(self.instance, "manufacturing_operation", None),
        )
        planned_start = attrs.get(
            "planned_start", getattr(self.instance, "planned_start", None)
        )
        due_at = attrs.get("due_at", getattr(self.instance, "due_at", None))
        started_at = attrs.get("started_at", getattr(self.instance, "started_at", None))
        completed_at = attrs.get(
            "completed_at", getattr(self.instance, "completed_at", None)
        )

        organization_id = employee.organization_id if employee else None
        if order and (
            order.organization_id != organization_id
            or (company and order.company_id != company.id)
        ):
            raise serializers.ValidationError(
                {"order_id": "Order must belong to the task organization and company."}
            )
        if operation and (
            operation.organization_id != organization_id
            or (company and operation.company_id != company.id)
        ):
            raise serializers.ValidationError(
                {
                    "manufacturing_operation_id": (
                        "Operation must belong to the task organization and company."
                    )
                }
            )
        if operation and order:
            source_order_id = operation.manufacturing_order.order_id
            if source_order_id and source_order_id != order.id:
                raise serializers.ValidationError(
                    {"order_id": "Order must match the manufacturing operation source order."}
                )
        if planned_start and due_at and due_at < planned_start:
            raise serializers.ValidationError(
                {"due_at": "Due date cannot precede planned start."}
            )
        if started_at and completed_at and completed_at < started_at:
            raise serializers.ValidationError(
                {"completed_at": "Completion cannot precede task start."}
            )
        return attrs


class EmployeeTimeEntrySerializer(ScopedWorkSerializer):
    task_id = serializers.PrimaryKeyRelatedField(
        source="task",
        queryset=EmployeeTask.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = EmployeeTimeEntry
        fields = (
            "id",
            "employee_id",
            "task_id",
            "company_id",
            "establishment_id",
            "workshop_id",
            "started_at",
            "ended_at",
            "duration_minutes",
            "source",
            "notes",
            "recorded_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "duration_minutes",
            "recorded_by_id",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        employee, company, _, _ = validate_scope(
            attrs, self.instance, self.context.get("request")
        )
        task = attrs.get("task", getattr(self.instance, "task", None))
        started_at = attrs.get("started_at", getattr(self.instance, "started_at", None))
        ended_at = attrs.get("ended_at", getattr(self.instance, "ended_at", None))
        if task:
            if employee and task.employee_id != employee.id:
                raise serializers.ValidationError(
                    {"task_id": "Time entry task must belong to the employee."}
                )
            if company and task.company_id != company.id:
                raise serializers.ValidationError(
                    {"task_id": "Time entry task must belong to the selected company."}
                )
        if started_at and ended_at and ended_at < started_at:
            raise serializers.ValidationError(
                {"ended_at": "End cannot precede start."}
            )
        return attrs

    @staticmethod
    def _duration_minutes(started_at, ended_at):
        if not ended_at:
            return 0
        return max(0, int((ended_at - started_at).total_seconds() // 60))

    def create(self, validated_data):
        validated_data["duration_minutes"] = self._duration_minutes(
            validated_data["started_at"], validated_data.get("ended_at")
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        started_at = validated_data.get("started_at", instance.started_at)
        ended_at = validated_data.get("ended_at", instance.ended_at)
        validated_data["duration_minutes"] = self._duration_minutes(started_at, ended_at)
        return super().update(instance, validated_data)
