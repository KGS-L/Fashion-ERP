from ivadoo.extensibility.defaults import BASE_PROTECTED
from ivadoo.extensibility.registry import (
    ModelManifest,
    ModuleManifest,
    register_model,
    register_module,
)


register_module(
    ModuleManifest(
        code="enterprise.employees",
        name="Employees",
        version="1.0.0",
        dependencies=("foundation",),
        default_enabled=True,
        edition="business",
        api_prefixes=("/api/v1/employees/",),
    )
)

register_model(
    ModelManifest(
        key="employees.employee",
        label="Employee",
        django_model="employees.Employee",
        module_code="enterprise.employees",
        view_permission="enterprise.employee.view",
        manage_permission="enterprise.employee.manage",
        protected_fields=BASE_PROTECTED | {"user", "user_id", "status"},
    )
)
register_model(
    ModelManifest(
        key="employees.skill",
        label="Employee skill",
        django_model="employees.Skill",
        module_code="enterprise.employees",
        view_permission="enterprise.employee.view",
        manage_permission="enterprise.employee.manage",
        protected_fields=BASE_PROTECTED,
    )
)
register_model(
    ModelManifest(
        key="employees.employeeskill",
        label="Employee skill link",
        django_model="employees.EmployeeSkill",
        module_code="enterprise.employees",
        view_permission="enterprise.employee.view",
        manage_permission="enterprise.employee.manage",
        protected_fields=BASE_PROTECTED | {"employee", "employee_id", "skill", "skill_id"},
    )
)
register_model(
    ModelManifest(
        key="employees.employeecontract",
        label="Employee contract",
        django_model="employees.EmployeeContract",
        module_code="enterprise.employees",
        view_permission="enterprise.employee.contract.view",
        manage_permission="enterprise.employee.contract.manage",
        protected_fields=BASE_PROTECTED
        | {
            "employee",
            "employee_id",
            "company",
            "company_id",
            "establishment",
            "establishment_id",
            "reference",
            "status",
        },
    )
)
register_model(
    ModelManifest(
        key="employees.employeeassignment",
        label="Employee assignment",
        django_model="employees.EmployeeAssignment",
        module_code="enterprise.employees",
        view_permission="enterprise.employee.view",
        manage_permission="enterprise.employee.manage",
        protected_fields=BASE_PROTECTED
        | {
            "employee",
            "employee_id",
            "company",
            "company_id",
            "establishment",
            "establishment_id",
            "workshop",
            "workshop_id",
            "role",
            "role_id",
            "start_date",
            "end_date",
        },
    )
)
register_model(
    ModelManifest(
        key="employees.employeeschedule",
        label="Employee schedule",
        django_model="employees.EmployeeSchedule",
        module_code="enterprise.employees",
        view_permission="enterprise.employee.work.view",
        manage_permission="enterprise.employee.work.manage",
        protected_fields=BASE_PROTECTED
        | {
            "employee",
            "employee_id",
            "company",
            "company_id",
            "establishment",
            "establishment_id",
            "workshop",
            "workshop_id",
            "status",
            "starts_at",
            "ends_at",
        },
    )
)
register_model(
    ModelManifest(
        key="employees.attendancerecord",
        label="Attendance record",
        django_model="employees.AttendanceRecord",
        module_code="enterprise.employees",
        view_permission="enterprise.employee.work.view",
        manage_permission="enterprise.employee.work.manage",
        protected_fields=BASE_PROTECTED
        | {
            "employee",
            "employee_id",
            "company",
            "company_id",
            "establishment",
            "establishment_id",
            "workshop",
            "workshop_id",
            "schedule",
            "schedule_id",
            "attendance_date",
            "status",
            "check_in_at",
            "check_out_at",
        },
    )
)
register_model(
    ModelManifest(
        key="employees.employeetask",
        label="Employee task",
        django_model="employees.EmployeeTask",
        module_code="enterprise.employees",
        view_permission="enterprise.employee.work.view",
        manage_permission="enterprise.employee.work.manage",
        protected_fields=BASE_PROTECTED
        | {
            "employee",
            "employee_id",
            "company",
            "company_id",
            "establishment",
            "establishment_id",
            "workshop",
            "workshop_id",
            "order",
            "order_id",
            "manufacturing_operation",
            "manufacturing_operation_id",
            "status",
        },
    )
)
register_model(
    ModelManifest(
        key="employees.employeetimeentry",
        label="Employee time entry",
        django_model="employees.EmployeeTimeEntry",
        module_code="enterprise.employees",
        view_permission="enterprise.employee.work.view",
        manage_permission="enterprise.employee.work.manage",
        protected_fields=BASE_PROTECTED
        | {
            "employee",
            "employee_id",
            "task",
            "task_id",
            "company",
            "company_id",
            "establishment",
            "establishment_id",
            "workshop",
            "workshop_id",
            "started_at",
            "ended_at",
            "duration_minutes",
        },
    )
)
