import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Employee(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="employees",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="employees",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="employee_profile",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=64)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    display_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    job_title = models.CharField(max_length=160, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    hire_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("display_name", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"),
                name="employee_unique_code_per_company",
            ),
            models.CheckConstraint(
                condition=(
                    Q(end_date__isnull=True)
                    | Q(hire_date__isnull=True)
                    | Q(end_date__gte=F("hire_date"))
                ),
                name="employee_end_date_not_before_hire_date",
            ),
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.organization_id:
            if self.company.organization_id != self.organization_id:
                raise ValidationError(
                    {"company": "Company must belong to the employee organization."}
                )
        if self.establishment_id:
            if self.establishment.company_id != self.company_id:
                raise ValidationError(
                    {"establishment": "Establishment must belong to the employee company."}
                )
        if self.user_id and self.user.organization_id != self.organization_id:
            raise ValidationError(
                {"user": "Linked user must belong to the employee organization."}
            )
        if self.hire_date and self.end_date and self.end_date < self.hire_date:
            raise ValidationError({"end_date": "End date cannot be before hire date."})

    def __str__(self):
        return self.display_name


class Skill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="employee_skills_catalog",
    )
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="employee_skill_unique_code_per_organization",
            )
        ]

    def __str__(self):
        return self.name


class EmployeeSkill(models.Model):
    class Proficiency(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"
        EXPERT = "expert", "Expert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="skills",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="employee_links",
    )
    proficiency = models.CharField(
        max_length=16,
        choices=Proficiency.choices,
        default=Proficiency.INTERMEDIATE,
    )
    is_specialty = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("employee_id", "skill__name")
        constraints = [
            models.UniqueConstraint(
                fields=("employee", "skill"),
                name="employee_skill_unique_link",
            )
        ]

    def clean(self):
        super().clean()
        if self.employee_id and self.skill_id:
            if self.employee.organization_id != self.skill.organization_id:
                raise ValidationError(
                    {"skill": "Skill must belong to the employee organization."}
                )


class EmployeeContract(models.Model):
    class ContractType(models.TextChoices):
        PERMANENT = "permanent", "Permanent"
        FIXED_TERM = "fixed_term", "Fixed term"
        CONTRACTOR = "contractor", "Contractor"
        INTERNSHIP = "internship", "Internship"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="contracts",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="employee_contracts",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_contracts",
        null=True,
        blank=True,
    )
    reference = models.CharField(max_length=80)
    contract_type = models.CharField(max_length=24, choices=ContractType.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    job_title = models.CharField(max_length=160, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    document_reference = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-start_date", "reference")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "reference"),
                name="employee_contract_unique_reference_per_company",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="employee_contract_end_not_before_start",
            ),
        ]

    def clean(self):
        super().clean()
        if self.employee_id and self.company_id:
            if self.employee.organization_id != self.company.organization_id:
                raise ValidationError(
                    {"company": "Contract company must belong to the employee organization."}
                )
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError(
                {"establishment": "Contract establishment must belong to the selected company."}
            )
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})

    def __str__(self):
        return self.reference


class EmployeeAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="employee_assignments",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_assignments",
        null=True,
        blank=True,
    )
    workshop = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_workshop_assignments",
        null=True,
        blank=True,
        limit_choices_to={"site_type__in": ("workshop", "mixed")},
    )
    role = models.ForeignKey(
        "authorization.Role",
        on_delete=models.PROTECT,
        related_name="employee_assignments",
    )
    title = models.CharField(max_length=160, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_primary", "-start_date", "employee_id")
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="employee_assignment_end_not_before_start",
            )
        ]

    def clean(self):
        super().clean()
        organization_id = self.employee.organization_id if self.employee_id else None
        if self.company_id and self.company.organization_id != organization_id:
            raise ValidationError(
                {"company": "Assignment company must belong to the employee organization."}
            )
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError(
                {"establishment": "Assignment establishment must belong to the selected company."}
            )
        if self.workshop_id:
            if self.workshop.company_id != self.company_id:
                raise ValidationError(
                    {"workshop": "Workshop must belong to the selected company."}
                )
            if self.workshop.site_type not in {"workshop", "mixed"}:
                raise ValidationError(
                    {"workshop": "Workshop must use the workshop or mixed establishment type."}
                )
        if self.role_id and self.role.organization_id != organization_id:
            raise ValidationError({"role": "Role must belong to the employee organization."})
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})

    def __str__(self):
        return f"{self.employee} — {self.role}"


from .work_models import (  # noqa: E402,F401
    AttendanceRecord,
    EmployeeSchedule,
    EmployeeTask,
    EmployeeTaskTransition,
    EmployeeTimeEntry,
)
from .performance_models import (  # noqa: E402,F401
    CommissionCalculation,
    CommissionRule,
    ProductivitySnapshot,
)
