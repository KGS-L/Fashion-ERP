import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from ivadoo.internationalization.constants import SUPPORTED_LANGUAGES
from ivadoo.internationalization.validators import validate_language_code


class CRMSource(models.Model):
    class SourceType(models.TextChoices):
        REFERRAL = "referral", "Referral"
        WEBSITE = "website", "Website"
        SOCIAL = "social", "Social media"
        ADVERTISING = "advertising", "Advertising"
        EVENT = "event", "Event"
        WALK_IN = "walk_in", "Walk in"
        PARTNER = "partner", "Partner"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="crm_sources",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="crm_sources",
    )
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    source_type = models.CharField(
        max_length=24,
        choices=SourceType.choices,
        default=SourceType.OTHER,
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("company__name", "name", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"),
                name="crm_source_unique_code_company",
            )
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.organization_id:
            if self.company.organization_id != self.organization_id:
                raise ValidationError(
                    {"company": "Company must belong to the CRM source organization."}
                )

    def __str__(self):
        return self.name


class CRMPipelineStage(models.Model):
    class StageType(models.TextChoices):
        OPEN = "open", "Open"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="crm_pipeline_stages",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="crm_pipeline_stages",
    )
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    position = models.PositiveIntegerField(default=10)
    stage_type = models.CharField(
        max_length=16,
        choices=StageType.choices,
        default=StageType.OPEN,
    )
    probability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("company__name", "position", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"),
                name="crm_stage_unique_code_company",
            ),
            models.UniqueConstraint(
                fields=("company", "position"),
                name="crm_stage_unique_position_company",
            ),
            models.CheckConstraint(
                condition=Q(probability__gte=0) & Q(probability__lte=100),
                name="crm_stage_probability_range",
            ),
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.organization_id:
            if self.company.organization_id != self.organization_id:
                raise ValidationError(
                    {"company": "Company must belong to the CRM stage organization."}
                )

    def __str__(self):
        return self.name


class CRMLead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        QUALIFIED = "qualified", "Qualified"
        DISQUALIFIED = "disqualified", "Disqualified"
        CONVERTED = "converted", "Converted"

    class ProspectType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        COMPANY = "company", "Company"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="crm_leads",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="crm_leads",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="crm_leads",
        null=True,
        blank=True,
    )
    source = models.ForeignKey(
        CRMSource,
        on_delete=models.PROTECT,
        related_name="leads",
        null=True,
        blank=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_crm_leads",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=64)
    prospect_type = models.CharField(
        max_length=16,
        choices=ProspectType.choices,
        default=ProspectType.INDIVIDUAL,
    )
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
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.NEW,
    )
    notes = models.TextField(blank=True)
    converted_customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="converted_crm_leads",
        null=True,
        blank=True,
    )
    converted_at = models.DateTimeField(null=True, blank=True)
    converted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="converted_crm_leads",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_crm_leads",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "display_name")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"),
                name="crm_lead_unique_code_company",
            )
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.organization_id:
            if self.company.organization_id != self.organization_id:
                raise ValidationError(
                    {"company": "Company must belong to the lead organization."}
                )
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError(
                {"establishment": "Establishment must belong to the selected company."}
            )
        if self.source_id and self.source.company_id != self.company_id:
            raise ValidationError({"source": "Source must belong to the selected company."})
        if self.owner_id and self.owner.organization_id != self.organization_id:
            raise ValidationError({"owner": "Owner must belong to the lead organization."})
        if self.converted_customer_id:
            customer = self.converted_customer
            if (
                customer.organization_id != self.organization_id
                or customer.company_id != self.company_id
            ):
                raise ValidationError(
                    {"converted_customer": "Converted customer must belong to the lead company."}
                )
        if self.converted_by_id and self.converted_by.organization_id != self.organization_id:
            raise ValidationError(
                {"converted_by": "Converter must belong to the lead organization."}
            )

    def __str__(self):
        return self.display_name


class CRMOpportunity(models.Model):
    class ProspectType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        COMPANY = "company", "Company"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="crm_opportunities",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="crm_opportunities",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="crm_opportunities",
        null=True,
        blank=True,
    )
    lead = models.ForeignKey(
        CRMLead,
        on_delete=models.PROTECT,
        related_name="opportunities",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="crm_opportunities",
        null=True,
        blank=True,
    )
    source = models.ForeignKey(
        CRMSource,
        on_delete=models.PROTECT,
        related_name="opportunities",
        null=True,
        blank=True,
    )
    stage = models.ForeignKey(
        CRMPipelineStage,
        on_delete=models.PROTECT,
        related_name="opportunities",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_crm_opportunities",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    prospect_type = models.CharField(
        max_length=16,
        choices=ProspectType.choices,
        default=ProspectType.INDIVIDUAL,
    )
    contact_name = models.CharField(max_length=255, blank=True)
    legal_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    language_code = models.CharField(
        max_length=8,
        choices=SUPPORTED_LANGUAGES,
        default="fr",
        validators=[validate_language_code],
    )
    expected_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.ForeignKey(
        "internationalization.Currency",
        on_delete=models.PROTECT,
        related_name="crm_opportunities",
        null=True,
        blank=True,
    )
    probability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    expected_close_date = models.DateField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    converted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="converted_crm_opportunities",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_crm_opportunities",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("stage__position", "-created_at", "title")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"),
                name="crm_opportunity_unique_code_company",
            ),
            models.CheckConstraint(
                condition=Q(expected_revenue__gte=0),
                name="crm_opportunity_revenue_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(probability__gte=0) & Q(probability__lte=100),
                name="crm_opportunity_probability_range",
            ),
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.organization_id:
            if self.company.organization_id != self.organization_id:
                raise ValidationError(
                    {"company": "Company must belong to the opportunity organization."}
                )
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError(
                {"establishment": "Establishment must belong to the selected company."}
            )
        if self.lead_id:
            if (
                self.lead.organization_id != self.organization_id
                or self.lead.company_id != self.company_id
            ):
                raise ValidationError({"lead": "Lead must belong to the opportunity company."})
        if self.customer_id:
            if (
                self.customer.organization_id != self.organization_id
                or self.customer.company_id != self.company_id
            ):
                raise ValidationError(
                    {"customer": "Customer must belong to the opportunity company."}
                )
        if self.source_id and self.source.company_id != self.company_id:
            raise ValidationError({"source": "Source must belong to the selected company."})
        if self.stage_id and self.stage.company_id != self.company_id:
            raise ValidationError({"stage": "Stage must belong to the selected company."})
        if self.owner_id and self.owner.organization_id != self.organization_id:
            raise ValidationError(
                {"owner": "Owner must belong to the opportunity organization."}
            )
        if self.converted_by_id and self.converted_by.organization_id != self.organization_id:
            raise ValidationError(
                {"converted_by": "Converter must belong to the opportunity organization."}
            )

    def __str__(self):
        return self.title


class CRMConversionEvent(models.Model):
    class SourceKind(models.TextChoices):
        LEAD = "lead", "Lead"
        OPPORTUNITY = "opportunity", "Opportunity"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="crm_conversion_events",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="crm_conversion_events",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="crm_conversion_events",
        null=True,
        blank=True,
    )
    source_kind = models.CharField(max_length=16, choices=SourceKind.choices)
    lead = models.ForeignKey(
        CRMLead,
        on_delete=models.PROTECT,
        related_name="conversion_events",
        null=True,
        blank=True,
    )
    opportunity = models.ForeignKey(
        CRMOpportunity,
        on_delete=models.PROTECT,
        related_name="conversion_events",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="crm_conversion_events",
    )
    created_customer = models.BooleanField(default=False)
    source_snapshot = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="crm_conversion_events",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(lead__isnull=False, opportunity__isnull=True)
                    | Q(lead__isnull=True, opportunity__isnull=False)
                ),
                name="crm_conversion_exactly_one_source",
            ),
            models.UniqueConstraint(
                fields=("lead",),
                condition=Q(lead__isnull=False),
                name="crm_conversion_one_per_lead",
            ),
            models.UniqueConstraint(
                fields=("opportunity",),
                condition=Q(opportunity__isnull=False),
                name="crm_conversion_one_per_opportunity",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("CRM conversion events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("CRM conversion events are immutable.")

    def __str__(self):
        return f"{self.source_kind} -> {self.customer_id}"
