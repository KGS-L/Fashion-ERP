from rest_framework import serializers

from ivadoo.authorization.models import Role
from ivadoo.identity.models import User
from ivadoo.organizations.models import Company, Establishment

from .models import Employee, EmployeeAssignment, EmployeeContract, EmployeeSkill, Skill


class EmployeeSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )
    establishment_id = serializers.PrimaryKeyRelatedField(
        source="establishment",
        queryset=Establishment.objects.all(),
        allow_null=True,
        required=False,
    )
    user_id = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=User.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Employee
        fields = (
            "id",
            "organization_id",
            "company_id",
            "establishment_id",
            "user_id",
            "code",
            "first_name",
            "last_name",
            "display_name",
            "email",
            "phone",
            "job_title",
            "status",
            "hire_date",
            "end_date",
            "notes",
            "created_at",
            "updated_at",
            "archived_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "created_at",
            "updated_at",
            "archived_at",
        )

    def validate(self, attrs):
        request = self.context.get("request")
        company = attrs.get("company", getattr(self.instance, "company", None))
        establishment = attrs.get(
            "establishment", getattr(self.instance, "establishment", None)
        )
        user = attrs.get("user", getattr(self.instance, "user", None))
        hire_date = attrs.get("hire_date", getattr(self.instance, "hire_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))

        if request and company and company.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"company_id": "Company is outside the local organization."}
            )
        if establishment and company and establishment.company_id != company.id:
            raise serializers.ValidationError(
                {"establishment_id": "Establishment must belong to the selected company."}
            )
        if request and user and user.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"user_id": "Linked user is outside the local organization."}
            )
        if hire_date and end_date and end_date < hire_date:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be before hire date."}
            )
        return attrs


class SkillSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Skill
        fields = (
            "id",
            "organization_id",
            "code",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")


class EmployeeSkillSerializer(serializers.ModelSerializer):
    employee_id = serializers.PrimaryKeyRelatedField(
        source="employee", queryset=Employee.objects.all()
    )
    skill_id = serializers.PrimaryKeyRelatedField(
        source="skill", queryset=Skill.objects.all()
    )

    class Meta:
        model = EmployeeSkill
        fields = (
            "id",
            "employee_id",
            "skill_id",
            "proficiency",
            "is_specialty",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        employee = attrs.get("employee", getattr(self.instance, "employee", None))
        skill = attrs.get("skill", getattr(self.instance, "skill", None))
        if request and employee and employee.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"employee_id": "Employee is outside the local organization."}
            )
        if request and skill and skill.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"skill_id": "Skill is outside the local organization."}
            )
        if employee and skill and employee.organization_id != skill.organization_id:
            raise serializers.ValidationError(
                {"skill_id": "Skill must belong to the employee organization."}
            )
        return attrs


class EmployeeContractSerializer(serializers.ModelSerializer):
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

    class Meta:
        model = EmployeeContract
        fields = (
            "id",
            "employee_id",
            "company_id",
            "establishment_id",
            "reference",
            "contract_type",
            "status",
            "job_title",
            "start_date",
            "end_date",
            "document_reference",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        employee = attrs.get("employee", getattr(self.instance, "employee", None))
        company = attrs.get("company", getattr(self.instance, "company", None))
        establishment = attrs.get(
            "establishment", getattr(self.instance, "establishment", None)
        )
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))

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
                {"company_id": "Contract company must belong to the employee organization."}
            )
        if establishment and company and establishment.company_id != company.id:
            raise serializers.ValidationError(
                {"establishment_id": "Establishment must belong to the selected company."}
            )
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be before start date."}
            )
        return attrs


class EmployeeAssignmentSerializer(serializers.ModelSerializer):
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
    role_id = serializers.PrimaryKeyRelatedField(
        source="role", queryset=Role.objects.all()
    )

    class Meta:
        model = EmployeeAssignment
        fields = (
            "id",
            "employee_id",
            "company_id",
            "establishment_id",
            "workshop_id",
            "role_id",
            "title",
            "start_date",
            "end_date",
            "is_primary",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        employee = attrs.get("employee", getattr(self.instance, "employee", None))
        company = attrs.get("company", getattr(self.instance, "company", None))
        establishment = attrs.get(
            "establishment", getattr(self.instance, "establishment", None)
        )
        workshop = attrs.get("workshop", getattr(self.instance, "workshop", None))
        role = attrs.get("role", getattr(self.instance, "role", None))
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))

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
                {"company_id": "Assignment company must belong to the employee organization."}
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
        if employee and role and role.organization_id != employee.organization_id:
            raise serializers.ValidationError(
                {"role_id": "Role must belong to the employee organization."}
            )
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be before start date."}
            )
        return attrs
