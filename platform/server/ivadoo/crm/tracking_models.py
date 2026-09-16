import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CRMSegment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="crm_segments",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="crm_segments",
    )
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("company__name", "name", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"),
                name="crm_segment_unique_code_company",
            )
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.organization_id:
            if self.company.organization_id != self.organization_id:
                raise ValidationError(
                    {"company": "Company must belong to the segment organization."}
                )

    def __str__(self):
        return self.name


class CRMSegmentMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="crm_segment_memberships",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="crm_segment_memberships",
    )
    segment = models.ForeignKey(
        CRMSegment,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    lead = models.ForeignKey(
        "crm.CRMLead",
        on_delete=models.PROTECT,
        related_name="segment_memberships",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="crm_segment_memberships",
        null=True,
        blank=True,
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="added_crm_segment_memberships",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("segment__name", "-added_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(lead__isnull=False, customer__isnull=True)
                    | Q(lead__isnull=True, customer__isnull=False)
                ),
                name="crm_segment_member_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=("segment", "lead"),
                condition=Q(lead__isnull=False),
                name="crm_segment_member_unique_lead",
            ),
            models.UniqueConstraint(
                fields=("segment", "customer"),
                condition=Q(customer__isnull=False),
                name="crm_segment_member_unique_customer",
            ),
        ]

    def clean(self):
        super().clean()
        targets = int(bool(self.lead_id)) + int(bool(self.customer_id))
        if targets != 1:
            raise ValidationError("A segment membership must target exactly one lead or customer.")
        if self.company_id and self.organization_id:
            if self.company.organization_id != self.organization_id:
                raise ValidationError({"company": "Company must belong to the membership organization."})
        if self.segment_id and self.segment.company_id != self.company_id:
            raise ValidationError({"segment": "Segment must belong to the selected company."})
        if self.lead_id:
            if self.lead.organization_id != self.organization_id or self.lead.company_id != self.company_id:
                raise ValidationError({"lead": "Lead must belong to the membership company."})
        if self.customer_id:
            if self.customer.organization_id != self.organization_id or self.customer.company_id != self.company_id:
                raise ValidationError({"customer": "Customer must belong to the membership company."})
        if self.added_by_id and self.added_by.organization_id != self.organization_id:
            raise ValidationError({"added_by": "User must belong to the membership organization."})


class CRMFollowUp(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="crm_followups",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="crm_followups",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="crm_followups",
        null=True,
        blank=True,
    )
    lead = models.ForeignKey(
        "crm.CRMLead",
        on_delete=models.PROTECT,
        related_name="followups",
        null=True,
        blank=True,
    )
    opportunity = models.ForeignKey(
        "crm.CRMOpportunity",
        on_delete=models.PROTECT,
        related_name="followups",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="crm_followups",
        null=True,
        blank=True,
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_crm_followups",
        null=True,
        blank=True,
    )
    subject = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_at = models.DateTimeField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    priority = models.CharField(
        max_length=16,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_crm_followups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("status", "due_at", "-created_at")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(lead__isnull=False, opportunity__isnull=True, customer__isnull=True)
                    | Q(lead__isnull=True, opportunity__isnull=False, customer__isnull=True)
                    | Q(lead__isnull=True, opportunity__isnull=True, customer__isnull=False)
                ),
                name="crm_followup_exactly_one_target",
            )
        ]
        indexes = [
            models.Index(
                fields=("company", "status", "due_at"),
                name="crm_followup_due_idx",
            )
        ]

    def clean(self):
        super().clean()
        targets = int(bool(self.lead_id)) + int(bool(self.opportunity_id)) + int(bool(self.customer_id))
        if targets != 1:
            raise ValidationError("A follow-up must target exactly one lead, opportunity or customer.")
        if self.company_id and self.organization_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company must belong to the follow-up organization."})
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError({"establishment": "Establishment must belong to the selected company."})
        for field_name in ("lead", "opportunity", "customer"):
            target = getattr(self, field_name, None)
            if target is not None and (
                target.organization_id != self.organization_id or target.company_id != self.company_id
            ):
                raise ValidationError({field_name: "Target must belong to the follow-up company."})
        if self.assignee_id and self.assignee.organization_id != self.organization_id:
            raise ValidationError({"assignee": "Assignee must belong to the follow-up organization."})
        if self.created_by_id and self.created_by.organization_id != self.organization_id:
            raise ValidationError({"created_by": "Creator must belong to the follow-up organization."})

    def __str__(self):
        return self.subject


class CRMInteraction(models.Model):
    class Channel(models.TextChoices):
        PHONE = "phone", "Phone"
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"
        IN_PERSON = "in_person", "In person"
        WEBSITE = "website", "Website"
        OTHER = "other", "Other"

    class Direction(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"
        INTERNAL = "internal", "Internal"

    class InteractionType(models.TextChoices):
        NOTE = "note", "Note"
        CALL = "call", "Call"
        MESSAGE = "message", "Message"
        MEETING = "meeting", "Meeting"
        VISIT = "visit", "Visit"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="crm_interactions",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="crm_interactions",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="crm_interactions",
        null=True,
        blank=True,
    )
    lead = models.ForeignKey(
        "crm.CRMLead",
        on_delete=models.PROTECT,
        related_name="interactions",
        null=True,
        blank=True,
    )
    opportunity = models.ForeignKey(
        "crm.CRMOpportunity",
        on_delete=models.PROTECT,
        related_name="interactions",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="crm_interactions",
        null=True,
        blank=True,
    )
    interaction_type = models.CharField(
        max_length=16,
        choices=InteractionType.choices,
        default=InteractionType.NOTE,
    )
    channel = models.CharField(
        max_length=16,
        choices=Channel.choices,
        default=Channel.OTHER,
    )
    direction = models.CharField(
        max_length=16,
        choices=Direction.choices,
        default=Direction.INTERNAL,
    )
    subject = models.CharField(max_length=255, blank=True)
    summary = models.TextField()
    occurred_at = models.DateTimeField(default=timezone.now)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="crm_interactions",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at", "-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(lead__isnull=False, opportunity__isnull=True, customer__isnull=True)
                    | Q(lead__isnull=True, opportunity__isnull=False, customer__isnull=True)
                    | Q(lead__isnull=True, opportunity__isnull=True, customer__isnull=False)
                ),
                name="crm_interaction_exactly_one_target",
            )
        ]
        indexes = [
            models.Index(
                fields=("company", "occurred_at"),
                name="crm_interaction_time_idx",
            )
        ]

    def clean(self):
        super().clean()
        targets = int(bool(self.lead_id)) + int(bool(self.opportunity_id)) + int(bool(self.customer_id))
        if targets != 1:
            raise ValidationError("An interaction must target exactly one lead, opportunity or customer.")
        if self.company_id and self.organization_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company must belong to the interaction organization."})
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError({"establishment": "Establishment must belong to the selected company."})
        for field_name in ("lead", "opportunity", "customer"):
            target = getattr(self, field_name, None)
            if target is not None and (
                target.organization_id != self.organization_id or target.company_id != self.company_id
            ):
                raise ValidationError({field_name: "Target must belong to the interaction company."})
        if self.actor_id and self.actor.organization_id != self.organization_id:
            raise ValidationError({"actor": "Actor must belong to the interaction organization."})

    def __str__(self):
        return self.subject or f"{self.interaction_type} {self.occurred_at.isoformat()}"
