import uuid

from django.core.exceptions import ValidationError
from django.db import models

from fashionerp.internationalization.constants import SUPPORTED_LANGUAGES
from fashionerp.internationalization.validators import validate_language_code


class Customer(models.Model):
    class CustomerType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        COMPANY = "company", "Company"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="customers",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="customers",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="customers",
        null=True,
        blank=True,
    )
    customer_type = models.CharField(
        max_length=16,
        choices=CustomerType.choices,
        default=CustomerType.INDIVIDUAL,
    )
    code = models.CharField(max_length=64)
    display_name = models.CharField(max_length=255)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    legal_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    language_code = models.CharField(
        max_length=8,
        choices=SUPPORTED_LANGUAGES,
        default="fr",
        validators=[validate_language_code],
    )
    preferred_currency = models.ForeignKey(
        "internationalization.Currency",
        on_delete=models.PROTECT,
        related_name="preferred_by_customers",
        null=True,
        blank=True,
    )
    preferences = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
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
                fields=("company", "code"),
                name="customer_unique_code_per_company",
            ),
        ]
        ordering = ("display_name", "code")

    def clean(self):
        super().clean()
        if self.company_id and self.organization_id:
            if self.company.organization_id != self.organization_id:
                raise ValidationError(
                    {"company": "Company must belong to the customer organization."}
                )
        if self.establishment_id:
            if self.establishment.company_id != self.company_id:
                raise ValidationError(
                    {"establishment": "Establishment must belong to the customer company."}
                )

    def __str__(self):
        return self.display_name


class CustomerContact(models.Model):
    class ContactType(models.TextChoices):
        EMAIL = "email", "Email"
        PHONE = "phone", "Phone"
        WHATSAPP = "whatsapp", "WhatsApp"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    contact_type = models.CharField(max_length=16, choices=ContactType.choices)
    label = models.CharField(max_length=80, blank=True)
    value = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("contact_type", "created_at")


class CustomerAddress(models.Model):
    class AddressType(models.TextChoices):
        BILLING = "billing", "Billing"
        SHIPPING = "shipping", "Shipping"
        HOME = "home", "Home"
        WORK = "work", "Work"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(
        max_length=16,
        choices=AddressType.choices,
        default=AddressType.OTHER,
    )
    label = models.CharField(max_length=80, blank=True)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=32, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("address_type", "created_at")


class CustomerConsent(models.Model):
    class ConsentType(models.TextChoices):
        MARKETING = "marketing", "Marketing"
        DATA_PROCESSING = "data_processing", "Data processing"
        PHOTO = "photo", "Photo usage"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="consents",
    )
    consent_type = models.CharField(max_length=32, choices=ConsentType.choices)
    granted = models.BooleanField(default=False)
    recorded_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=80, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("consent_type", "-recorded_at")
