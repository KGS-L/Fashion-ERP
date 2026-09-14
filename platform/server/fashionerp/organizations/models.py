import uuid

from django.core.exceptions import ValidationError
from django.db import models

from fashionerp.internationalization.constants import SUPPORTED_LANGUAGES
from fashionerp.internationalization.validators import (
    validate_language_code,
    validate_timezone_name,
)


class Organization(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    singleton_key = models.BooleanField(default=True, unique=True, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(singleton_key=True),
                name="organization_singleton_key_true",
            ),
        ]
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Company(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="companies",
    )
    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=64)
    legal_name = models.CharField(max_length=255, blank=True)
    registration_number = models.CharField(max_length=128, blank=True)
    tax_identifier = models.CharField(max_length=128, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    language_code = models.CharField(
        max_length=8,
        choices=SUPPORTED_LANGUAGES,
        default="fr",
        validators=[validate_language_code],
    )
    functional_currency = models.ForeignKey(
        "internationalization.Currency",
        on_delete=models.PROTECT,
        related_name="functional_currency_companies",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="company_unique_code_per_organization",
            ),
        ]
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Establishment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    class SiteType(models.TextChoices):
        WORKSHOP = "workshop", "Workshop"
        STORE = "store", "Store"
        WAREHOUSE = "warehouse", "Warehouse"
        OFFICE = "office", "Office"
        MIXED = "mixed", "Mixed"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="establishments",
    )
    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=64)
    site_type = models.CharField(
        max_length=16,
        choices=SiteType.choices,
        default=SiteType.OTHER,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    timezone = models.CharField(
        max_length=64,
        default="UTC",
        validators=[validate_timezone_name],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"),
                name="establishment_unique_code_per_company",
            ),
        ]
        ordering = ("name",)

    @property
    def organization_id(self):
        return self.company.organization_id

    def clean(self) -> None:
        super().clean()
        if self.company_id and not Company.objects.filter(pk=self.company_id).exists():
            raise ValidationError({"company": "Company does not exist."})

    def __str__(self) -> str:
        return self.name
