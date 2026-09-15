from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated

from ivadoo.audit.services import audit_snapshot, record_audit_event
from ivadoo.authorization.services import (
    authorized_company_ids,
    authorized_establishment_ids,
    has_any_scope_permission,
    has_permission,
)

from .models import Employee, EmployeeAssignment, EmployeeContract, EmployeeSkill, Skill
from .serializers import (
    EmployeeAssignmentSerializer,
    EmployeeContractSerializer,
    EmployeeSerializer,
    EmployeeSkillSerializer,
    SkillSerializer,
)


EMPLOYEE_VIEW = "enterprise.employee.view"
EMPLOYEE_MANAGE = "enterprise.employee.manage"
CONTRACT_VIEW = "enterprise.employee.contract.view"
CONTRACT_MANAGE = "enterprise.employee.contract.manage"


def scoped_employees(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    establishment_ids = authorized_establishment_ids(user, permission_code)
    if not company_ids and not establishment_ids:
        return Employee.objects.none()

    return (
        Employee.objects.filter(organization_id=user.organization_id)
        .filter(
            Q(company_id__in=company_ids)
            | Q(establishment_id__in=establishment_ids)
            | Q(assignments__company_id__in=company_ids)
            | Q(assignments__establishment_id__in=establishment_ids)
            | Q(assignments__workshop_id__in=establishment_ids)
        )
        .select_related("company", "establishment", "user")
        .distinct()
    )


def scoped_employee_skills(user, permission_code):
    employee_ids = scoped_employees(user, permission_code).values_list("id", flat=True)
    return EmployeeSkill.objects.filter(employee_id__in=employee_ids).select_related(
        "employee", "skill"
    )


def scoped_contracts(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    establishment_ids = authorized_establishment_ids(user, permission_code)
    if not company_ids and not establishment_ids:
        return EmployeeContract.objects.none()
    return EmployeeContract.objects.filter(
        employee__organization_id=user.organization_id
    ).filter(
        Q(company_id__in=company_ids) | Q(establishment_id__in=establishment_ids)
    ).select_related("employee", "company", "establishment")


def scoped_assignments(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    establishment_ids = authorized_establishment_ids(user, permission_code)
    if not company_ids and not establishment_ids:
        return EmployeeAssignment.objects.none()
    return EmployeeAssignment.objects.filter(
        employee__organization_id=user.organization_id
    ).filter(
        Q(company_id__in=company_ids)
        | Q(establishment_id__in=establishment_ids)
        | Q(workshop_id__in=establishment_ids)
    ).select_related("employee", "company", "establishment", "workshop", "role")


def record_change(*, request, action, instance, before=None):
    record_audit_event(
        organization=request.user.organization,
        actor=request.user,
        action=action,
        object_instance=instance,
        before=before,
        after=audit_snapshot(instance),
        request=request,
    )


class EmployeeListView(generics.ListCreateAPIView):
    queryset = Employee.objects.none()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ("company_id", "establishment_id", "status", "job_title")
    search_fields = (
        "code",
        "display_name",
        "first_name",
        "last_name",
        "email",
        "phone",
        "job_title",
    )
    ordering_fields = ("display_name", "code", "hire_date", "created_at", "updated_at")
    ordering = ("display_name",)

    def get_queryset(self):
        return scoped_employees(self.request.user, EMPLOYEE_VIEW)

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        establishment = serializer.validated_data.get("establishment")
        if not has_permission(
            self.request.user,
            EMPLOYEE_MANAGE,
            company=company,
            establishment=establishment,
        ):
            raise PermissionDenied("You cannot manage employees in this scope.")
        with transaction.atomic():
            employee = serializer.save(organization=self.request.user.organization)
            record_change(
                request=self.request,
                action="enterprise.employee.create",
                instance=employee,
            )


class EmployeeDetailView(generics.RetrieveUpdateAPIView):
    queryset = Employee.objects.none()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "employee_id"

    def get_queryset(self):
        permission = EMPLOYEE_VIEW if self.request.method == "GET" else EMPLOYEE_MANAGE
        return scoped_employees(self.request.user, permission)

    def perform_update(self, serializer):
        company = serializer.validated_data.get("company", serializer.instance.company)
        establishment = serializer.validated_data.get(
            "establishment", serializer.instance.establishment
        )
        if not has_permission(
            self.request.user,
            EMPLOYEE_MANAGE,
            company=company,
            establishment=establishment,
        ):
            raise PermissionDenied("You cannot move or update an employee in this scope.")
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            employee = serializer.save()
            record_change(
                request=self.request,
                action="enterprise.employee.update",
                instance=employee,
                before=before,
            )


class SkillListView(generics.ListCreateAPIView):
    queryset = Skill.objects.none()
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ("is_active",)
    search_fields = ("code", "name", "description")
    ordering_fields = ("name", "code", "created_at", "updated_at")
    ordering = ("name",)

    def get_queryset(self):
        if not has_any_scope_permission(self.request.user, EMPLOYEE_VIEW):
            return Skill.objects.none()
        return Skill.objects.filter(organization_id=self.request.user.organization_id)

    def perform_create(self, serializer):
        if not has_any_scope_permission(self.request.user, EMPLOYEE_MANAGE):
            raise PermissionDenied("You cannot manage employee skills.")
        with transaction.atomic():
            skill = serializer.save(organization=self.request.user.organization)
            record_change(
                request=self.request,
                action="enterprise.employee_skill_catalog.create",
                instance=skill,
            )


class SkillDetailView(generics.RetrieveUpdateAPIView):
    queryset = Skill.objects.none()
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "skill_id"

    def get_queryset(self):
        permission = EMPLOYEE_VIEW if self.request.method == "GET" else EMPLOYEE_MANAGE
        if not has_any_scope_permission(self.request.user, permission):
            return Skill.objects.none()
        return Skill.objects.filter(organization_id=self.request.user.organization_id)

    def perform_update(self, serializer):
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            skill = serializer.save()
            record_change(
                request=self.request,
                action="enterprise.employee_skill_catalog.update",
                instance=skill,
                before=before,
            )


class EmployeeSkillListView(generics.ListCreateAPIView):
    queryset = EmployeeSkill.objects.none()
    serializer_class = EmployeeSkillSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ("employee_id", "skill_id", "proficiency", "is_specialty")
    ordering_fields = ("created_at", "updated_at")
    ordering = ("employee_id",)

    def get_queryset(self):
        return scoped_employee_skills(self.request.user, EMPLOYEE_VIEW)

    def perform_create(self, serializer):
        employee = serializer.validated_data["employee"]
        if not scoped_employees(self.request.user, EMPLOYEE_MANAGE).filter(
            pk=employee.pk
        ).exists():
            raise PermissionDenied("You cannot manage skills for this employee.")
        with transaction.atomic():
            link = serializer.save()
            record_change(
                request=self.request,
                action="enterprise.employee_skill.create",
                instance=link,
            )


class EmployeeSkillDetailView(generics.RetrieveUpdateAPIView):
    queryset = EmployeeSkill.objects.none()
    serializer_class = EmployeeSkillSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "employee_skill_id"

    def get_queryset(self):
        permission = EMPLOYEE_VIEW if self.request.method == "GET" else EMPLOYEE_MANAGE
        return scoped_employee_skills(self.request.user, permission)

    def perform_update(self, serializer):
        employee = serializer.validated_data.get("employee", serializer.instance.employee)
        if not scoped_employees(self.request.user, EMPLOYEE_MANAGE).filter(
            pk=employee.pk
        ).exists():
            raise PermissionDenied("You cannot manage skills for this employee.")
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            link = serializer.save()
            record_change(
                request=self.request,
                action="enterprise.employee_skill.update",
                instance=link,
                before=before,
            )


class EmployeeContractListView(generics.ListCreateAPIView):
    queryset = EmployeeContract.objects.none()
    serializer_class = EmployeeContractSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = (
        "employee_id",
        "company_id",
        "establishment_id",
        "contract_type",
        "status",
    )
    search_fields = ("reference", "job_title", "document_reference")
    ordering_fields = ("start_date", "end_date", "created_at", "updated_at")
    ordering = ("-start_date",)

    def get_queryset(self):
        return scoped_contracts(self.request.user, CONTRACT_VIEW)

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        establishment = serializer.validated_data.get("establishment")
        if not has_permission(
            self.request.user,
            CONTRACT_MANAGE,
            company=company,
            establishment=establishment,
        ):
            raise PermissionDenied("You cannot manage employee contracts in this scope.")
        with transaction.atomic():
            contract = serializer.save()
            record_change(
                request=self.request,
                action="enterprise.employee_contract.create",
                instance=contract,
            )


class EmployeeContractDetailView(generics.RetrieveUpdateAPIView):
    queryset = EmployeeContract.objects.none()
    serializer_class = EmployeeContractSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "contract_id"

    def get_queryset(self):
        permission = CONTRACT_VIEW if self.request.method == "GET" else CONTRACT_MANAGE
        return scoped_contracts(self.request.user, permission)

    def perform_update(self, serializer):
        company = serializer.validated_data.get("company", serializer.instance.company)
        establishment = serializer.validated_data.get(
            "establishment", serializer.instance.establishment
        )
        if not has_permission(
            self.request.user,
            CONTRACT_MANAGE,
            company=company,
            establishment=establishment,
        ):
            raise PermissionDenied("You cannot update employee contracts in this scope.")
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            contract = serializer.save()
            record_change(
                request=self.request,
                action="enterprise.employee_contract.update",
                instance=contract,
                before=before,
            )


class EmployeeAssignmentListView(generics.ListCreateAPIView):
    queryset = EmployeeAssignment.objects.none()
    serializer_class = EmployeeAssignmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = (
        "employee_id",
        "company_id",
        "establishment_id",
        "workshop_id",
        "role_id",
        "is_primary",
    )
    ordering_fields = ("start_date", "end_date", "created_at", "updated_at")
    ordering = ("-is_primary", "-start_date")

    def get_queryset(self):
        return scoped_assignments(self.request.user, EMPLOYEE_VIEW)

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        establishment = serializer.validated_data.get("establishment")
        workshop = serializer.validated_data.get("workshop")
        target_site = workshop or establishment
        if not has_permission(
            self.request.user,
            EMPLOYEE_MANAGE,
            company=company,
            establishment=target_site,
        ):
            raise PermissionDenied("You cannot manage employee assignments in this scope.")
        with transaction.atomic():
            assignment = serializer.save()
            record_change(
                request=self.request,
                action="enterprise.employee_assignment.create",
                instance=assignment,
            )


class EmployeeAssignmentDetailView(generics.RetrieveUpdateAPIView):
    queryset = EmployeeAssignment.objects.none()
    serializer_class = EmployeeAssignmentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "assignment_id"

    def get_queryset(self):
        permission = EMPLOYEE_VIEW if self.request.method == "GET" else EMPLOYEE_MANAGE
        return scoped_assignments(self.request.user, permission)

    def perform_update(self, serializer):
        company = serializer.validated_data.get("company", serializer.instance.company)
        establishment = serializer.validated_data.get(
            "establishment", serializer.instance.establishment
        )
        workshop = serializer.validated_data.get("workshop", serializer.instance.workshop)
        target_site = workshop or establishment
        if not has_permission(
            self.request.user,
            EMPLOYEE_MANAGE,
            company=company,
            establishment=target_site,
        ):
            raise PermissionDenied("You cannot update employee assignments in this scope.")
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            assignment = serializer.save()
            record_change(
                request=self.request,
                action="enterprise.employee_assignment.update",
                instance=assignment,
                before=before,
            )
