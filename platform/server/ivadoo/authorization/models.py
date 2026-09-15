import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Permission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=160, unique=True)
    module = models.CharField(max_length=80)
    action = models.CharField(max_length=80)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.code


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="access_roles",
    )
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        Permission,
        related_name="roles",
        blank=True,
    )
    is_full_access = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="role_unique_code_per_organization",
            ),
        ]
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class AccessGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="access_groups",
    )
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="access_groups",
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="access_group_unique_code_per_organization",
            ),
        ]
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class AccessGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="grants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_grants",
        null=True,
        blank=True,
    )
    group = models.ForeignKey(
        AccessGroup,
        on_delete=models.CASCADE,
        related_name="access_grants",
        null=True,
        blank=True,
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.CASCADE,
        related_name="access_grants",
        null=True,
        blank=True,
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.CASCADE,
        related_name="access_grants",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, group__isnull=True)
                    | models.Q(user__isnull=True, group__isnull=False)
                ),
                name="access_grant_exactly_one_principal",
            ),
            models.CheckConstraint(
                condition=~models.Q(
                    company__isnull=False,
                    establishment__isnull=False,
                ),
                name="access_grant_single_scope_target",
            ),
        ]
        ordering = ("-created_at",)

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def scope_type(self) -> str:
        if self.establishment_id:
            return "establishment"
        if self.company_id:
            return "company"
        return "organization"

    def clean(self) -> None:
        super().clean()

        principal_org_id = None
        if self.user_id:
            principal_org_id = self.user.organization_id
        elif self.group_id:
            principal_org_id = self.group.organization_id

        if principal_org_id and self.role.organization_id != principal_org_id:
            raise ValidationError("Role and principal must belong to the same organization.")

        if self.company_id and self.company.organization_id != self.role.organization_id:
            raise ValidationError("Company scope must belong to the role organization.")

        if (
            self.establishment_id
            and self.establishment.company.organization_id != self.role.organization_id
        ):
            raise ValidationError(
                "Establishment scope must belong to the role organization."
            )

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])
