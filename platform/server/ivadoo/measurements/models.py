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


class MeasurementSet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT,
        related_name="measurement_sets",
    )
    company = models.ForeignKey(
        "organizations.Company", on_delete=models.PROTECT,
        related_name="measurement_sets",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment", on_delete=models.PROTECT,
        related_name="measurement_sets", null=True, blank=True,
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT,
        related_name="measurement_sets",
    )
    profile = models.ForeignKey(
        MeasurementProfile, on_delete=models.PROTECT,
        related_name="measurement_sets", null=True, blank=True,
    )
    version = models.PositiveIntegerField()
    measured_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    alteration_notes = models.TextField(blank=True)
    media_references = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT,
        related_name="created_measurement_sets",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("customer", "version"),
                name="measurement_set_unique_customer_version",
            ),
        ]
        ordering = ("-measured_at", "-version")

    def clean(self):
        super().clean()
        if self.customer_id:
            if self.customer.organization_id != self.organization_id:
                raise ValidationError({"customer": "Customer must belong to the organization."})
            if self.customer.company_id != self.company_id:
                raise ValidationError({"company": "Company must match the customer company."})
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError({"establishment": "Establishment must belong to the company."})
        if self.profile_id and self.profile.organization_id != self.organization_id:
            raise ValidationError({"profile": "Profile must belong to the organization."})


class MeasurementValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    measurement_set = models.ForeignKey(
        MeasurementSet, on_delete=models.CASCADE, related_name="values"
    )
    definition = models.ForeignKey(
        MeasurementDefinition, on_delete=models.PROTECT,
        related_name="measurement_values",
    )
    value = models.DecimalField(max_digits=14, decimal_places=4)
    tolerance = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    note = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("measurement_set", "definition"),
                name="measurement_value_unique_definition_per_set",
            ),
            models.CheckConstraint(
                condition=models.Q(value__gte=0),
                name="measurement_value_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(tolerance__gte=0) | models.Q(tolerance__isnull=True),
                name="measurement_value_nonnegative_tolerance",
            ),
        ]
        ordering = ("definition__name",)

    def clean(self):
        super().clean()
        if self.measurement_set_id and self.definition_id:
            if self.measurement_set.organization_id != self.definition.organization_id:
                raise ValidationError(
                    {"definition": "Definition must belong to the measurement set organization."}
                )
