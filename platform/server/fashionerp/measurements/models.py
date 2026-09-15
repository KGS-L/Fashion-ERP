import uuid

from django.core.exceptions import ValidationError
from django.db import models


class MeasurementDefinition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT,
        related_name="measurement_definitions",
    )
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    unit = models.ForeignKey(
        "internationalization.UnitOfMeasure", on_delete=models.PROTECT,
        related_name="measurement_definitions",
    )
    default_tolerance = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="measurement_definition_unique_code_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(default_tolerance__gte=0)
                | models.Q(default_tolerance__isnull=True),
                name="measurement_definition_nonnegative_tolerance",
            ),
        ]
        ordering = ("name",)

    def clean(self):
        super().clean()
        if self.unit_id and self.organization_id:
            if self.unit.organization_id != self.organization_id:
                raise ValidationError({"unit": "Unit must belong to the organization."})


class MeasurementProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT,
        related_name="measurement_profiles",
    )
    company = models.ForeignKey(
        "organizations.Company", on_delete=models.PROTECT,
        related_name="measurement_profiles", null=True, blank=True,
    )
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    garment_type = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="measurement_profile_unique_code_per_org",
            ),
        ]
        ordering = ("garment_type", "name")

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company must belong to the organization."})


class MeasurementProfileItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        MeasurementProfile, on_delete=models.CASCADE, related_name="items"
    )
    definition = models.ForeignKey(
        MeasurementDefinition, on_delete=models.PROTECT, related_name="profile_items"
    )
    position = models.PositiveIntegerField()
    is_required = models.BooleanField(default=True)
    tolerance_override = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    instruction = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("profile", "definition"),
                name="measurement_profile_unique_definition",
            ),
            models.UniqueConstraint(
                fields=("profile", "position"),
                name="measurement_profile_unique_position",
            ),
            models.CheckConstraint(
                condition=models.Q(tolerance_override__gte=0)
                | models.Q(tolerance_override__isnull=True),
                name="measurement_profile_nonnegative_tolerance",
            ),
        ]
        ordering = ("position",)

    def clean(self):
        super().clean()
        if self.profile_id and self.definition_id:
            if self.profile.organization_id != self.definition.organization_id:
                raise ValidationError(
                    {"definition": "Definition must belong to the profile organization."}
                )
