from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ivadoo.customers.models import Customer

from .models import CRMConversionEvent, CRMLead, CRMOpportunity


def _matching_customers(*, company, email: str = "", phone: str = ""):
    email = (email or "").strip()
    phone = (phone or "").strip()
    query = Q()
    if email:
        query |= Q(email__iexact=email)
    if phone:
        query |= Q(phone=phone)
    if not query.children:
        return Customer.objects.none()
    return Customer.objects.filter(
        company=company,
    ).exclude(
        status=Customer.CustomerStatus.ARCHIVED,
    ).filter(query).order_by("created_at", "id")


def _resolve_or_create_customer(
    *,
    organization,
    company,
    establishment,
    customer,
    customer_code,
    prospect_type,
    display_name,
    first_name="",
    last_name="",
    legal_name="",
    email="",
    phone="",
    language_code="fr",
    preferred_currency=None,
    notes="",
):
    if customer is not None:
        if (
            customer.organization_id != organization.id
            or customer.company_id != company.id
        ):
            raise ValidationError(
                {"customer_id": "Customer must belong to the selected CRM company."}
            )
        return customer, False

    candidates = list(
        _matching_customers(company=company, email=email, phone=phone)[:3]
    )
    if len(candidates) == 1:
        return candidates[0], False
    if len(candidates) > 1:
        raise ValidationError(
            {
                "customer_id": {
                    "message": "Multiple existing customers match this prospect. Select the intended customer explicitly.",
                    "candidate_ids": [str(item.id) for item in candidates],
                }
            }
        )

    customer_code = (customer_code or "").strip()
    if not customer_code:
        raise ValidationError(
            {"customer_code": "A customer code is required when creating a new customer."}
        )
    if Customer.objects.filter(company=company, code=customer_code).exists():
        raise ValidationError(
            {"customer_code": "This customer code already exists in the selected company."}
        )

    created_customer = Customer(
        organization=organization,
        company=company,
        establishment=establishment,
        customer_type=prospect_type,
        code=customer_code,
        display_name=display_name,
        first_name=first_name,
        last_name=last_name,
        legal_name=legal_name,
        email=(email or "").strip(),
        phone=(phone or "").strip(),
        language_code=language_code or "fr",
        preferred_currency=preferred_currency,
        notes=notes,
        status=Customer.CustomerStatus.ACTIVE,
    )
    created_customer.full_clean()
    created_customer.save()
    return created_customer, True


def _lead_snapshot(lead):
    return {
        "id": str(lead.id),
        "code": lead.code,
        "display_name": lead.display_name,
        "prospect_type": lead.prospect_type,
        "email": lead.email,
        "phone": lead.phone,
        "language_code": lead.language_code,
        "status": lead.status,
        "source_id": str(lead.source_id) if lead.source_id else None,
        "owner_id": str(lead.owner_id) if lead.owner_id else None,
        "company_id": str(lead.company_id),
        "establishment_id": str(lead.establishment_id) if lead.establishment_id else None,
        "updated_at": lead.updated_at.isoformat(),
    }


def _opportunity_snapshot(opportunity):
    return {
        "id": str(opportunity.id),
        "code": opportunity.code,
        "title": opportunity.title,
        "prospect_type": opportunity.prospect_type,
        "contact_name": opportunity.contact_name,
        "email": opportunity.email,
        "phone": opportunity.phone,
        "language_code": opportunity.language_code,
        "lead_id": str(opportunity.lead_id) if opportunity.lead_id else None,
        "customer_id": str(opportunity.customer_id) if opportunity.customer_id else None,
        "source_id": str(opportunity.source_id) if opportunity.source_id else None,
        "stage_id": str(opportunity.stage_id),
        "owner_id": str(opportunity.owner_id) if opportunity.owner_id else None,
        "expected_revenue": str(opportunity.expected_revenue),
        "currency_id": opportunity.currency_id,
        "probability": str(opportunity.probability),
        "company_id": str(opportunity.company_id),
        "establishment_id": (
            str(opportunity.establishment_id) if opportunity.establishment_id else None
        ),
        "updated_at": opportunity.updated_at.isoformat(),
    }


def _mark_lead_converted(*, lead, customer, actor, created_customer):
    existing = CRMConversionEvent.objects.filter(lead=lead).select_related("customer").first()
    if existing:
        if existing.customer_id != customer.id:
            raise ValidationError(
                {"customer_id": "Lead was already converted to another customer."}
            )
        return existing

    if lead.status == CRMLead.Status.DISQUALIFIED:
        raise ValidationError({"lead_id": "A disqualified lead cannot be converted."})

    snapshot = _lead_snapshot(lead)
    lead.status = CRMLead.Status.CONVERTED
    lead.converted_customer = customer
    lead.converted_at = timezone.now()
    lead.converted_by = actor
    lead.full_clean()
    lead.save(
        update_fields=(
            "status",
            "converted_customer",
            "converted_at",
            "converted_by",
            "updated_at",
        )
    )
    return CRMConversionEvent.objects.create(
        organization=lead.organization,
        company=lead.company,
        establishment=lead.establishment,
        source_kind=CRMConversionEvent.SourceKind.LEAD,
        lead=lead,
        customer=customer,
        created_customer=created_customer,
        source_snapshot=snapshot,
        actor=actor,
    )


@transaction.atomic
def convert_lead(*, lead, actor, customer=None, customer_code=""):
    lead = (
        CRMLead.objects.select_for_update(of=("self",))
        .select_related(
            "organization",
            "company",
            "company__functional_currency",
            "establishment",
            "converted_customer",
        )
        .get(pk=lead.pk)
    )
    existing = CRMConversionEvent.objects.filter(lead=lead).select_related("customer").first()
    if existing:
        if customer is not None and existing.customer_id != customer.id:
            raise ValidationError(
                {"customer_id": "Lead was already converted to another customer."}
            )
        return existing
    if lead.status == CRMLead.Status.DISQUALIFIED:
        raise ValidationError({"lead_id": "A disqualified lead cannot be converted."})

    target_customer, created_customer = _resolve_or_create_customer(
        organization=lead.organization,
        company=lead.company,
        establishment=lead.establishment,
        customer=customer or lead.converted_customer,
        customer_code=customer_code,
        prospect_type=lead.prospect_type,
        display_name=lead.display_name,
        first_name=lead.first_name,
        last_name=lead.last_name,
        legal_name=lead.legal_name,
        email=lead.email,
        phone=lead.phone,
        language_code=lead.language_code,
        preferred_currency=lead.company.functional_currency,
        notes=lead.notes,
    )
    return _mark_lead_converted(
        lead=lead,
        customer=target_customer,
        actor=actor,
        created_customer=created_customer,
    )


@transaction.atomic
def convert_opportunity(*, opportunity, actor, customer=None, customer_code=""):
    opportunity = (
        CRMOpportunity.objects.select_for_update(of=("self",))
        .select_related(
            "organization",
            "company",
            "company__functional_currency",
            "establishment",
            "customer",
            "currency",
            "stage",
        )
        .get(pk=opportunity.pk)
    )
    existing = (
        CRMConversionEvent.objects.filter(opportunity=opportunity)
        .select_related("customer")
        .first()
    )
    if existing:
        if customer is not None and existing.customer_id != customer.id:
            raise ValidationError(
                {"customer_id": "Opportunity was already converted to another customer."}
            )
        return existing

    lead = None
    if opportunity.lead_id:
        lead = (
            CRMLead.objects.select_for_update(of=("self",))
            .select_related("converted_customer")
            .get(pk=opportunity.lead_id)
        )
    lead_customer = lead.converted_customer if lead and lead.converted_customer_id else None
    preselected_customer = customer or opportunity.customer or lead_customer

    if lead:
        prospect_type = lead.prospect_type
        display_name = lead.display_name
        first_name = lead.first_name
        last_name = lead.last_name
        legal_name = lead.legal_name
        email = lead.email
        phone = lead.phone
        language_code = lead.language_code
        notes = lead.notes or opportunity.description
    else:
        prospect_type = opportunity.prospect_type
        display_name = opportunity.contact_name or opportunity.title
        first_name = ""
        last_name = ""
        legal_name = opportunity.legal_name
        email = opportunity.email
        phone = opportunity.phone
        language_code = opportunity.language_code
        notes = opportunity.description

    target_customer, created_customer = _resolve_or_create_customer(
        organization=opportunity.organization,
        company=opportunity.company,
        establishment=opportunity.establishment,
        customer=preselected_customer,
        customer_code=customer_code,
        prospect_type=prospect_type,
        display_name=display_name,
        first_name=first_name,
        last_name=last_name,
        legal_name=legal_name,
        email=email,
        phone=phone,
        language_code=language_code,
        preferred_currency=(
            opportunity.currency or opportunity.company.functional_currency
        ),
        notes=notes,
    )

    if lead:
        _mark_lead_converted(
            lead=lead,
            customer=target_customer,
            actor=actor,
            created_customer=created_customer,
        )

    snapshot = _opportunity_snapshot(opportunity)
    opportunity.customer = target_customer
    opportunity.converted_at = timezone.now()
    opportunity.converted_by = actor
    opportunity.full_clean()
    opportunity.save(
        update_fields=("customer", "converted_at", "converted_by", "updated_at")
    )
    return CRMConversionEvent.objects.create(
        organization=opportunity.organization,
        company=opportunity.company,
        establishment=opportunity.establishment,
        source_kind=CRMConversionEvent.SourceKind.OPPORTUNITY,
        opportunity=opportunity,
        customer=target_customer,
        created_customer=created_customer,
        source_snapshot=snapshot,
        actor=actor,
    )
