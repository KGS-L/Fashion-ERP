from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.db.models import Model

from .models import AuditEvent


SAFE_FIELDS = {
    "customers.customer": (
        "organization_id", "company_id", "establishment_id", "customer_type",
        "code", "display_name", "first_name", "last_name", "legal_name",
        "email", "phone", "language_code", "preferred_currency_id",
        "preferences", "notes", "status", "archived_at",
    ),
    "identity.user": (
        "username", "first_name", "last_name", "email", "language_code", "is_active",
    ),
    "identity.apisession": (
        "device_id", "device_label", "user_agent", "ip_address", "two_factor_verified",
        "created_at", "expires_at", "idle_expires_at", "revoked_at", "revocation_reason",
    ),
    "authorization.role": (
        "code", "name", "description", "is_full_access", "is_system", "is_active",
    ),
    "authorization.accessgroup": ("code", "name", "description", "is_active"),
    "authorization.accessgrant": (
        "role_id", "user_id", "group_id", "company_id", "establishment_id", "created_at", "revoked_at",
    ),
    "organizations.company": (
        "organization_id", "name", "code", "legal_name", "registration_number", "tax_identifier",
        "country_code", "language_code", "functional_currency_id", "status", "archived_at",
    ),
    "internationalization.currency": ("code", "name", "symbol", "decimal_places", "rounding", "is_active"),
    "internationalization.exchangerate": (
        "organization_id", "base_currency_id", "quote_currency_id", "valid_on", "rate", "created_at",
    ),
    "internationalization.unitofmeasure": (
        "organization_id", "code", "name", "symbol", "category", "ratio_to_base", "rounding", "is_active",
    ),
    "organizations.establishment": (
        "company_id", "name", "code", "site_type", "status", "address_line1", "address_line2", "city",
        "region", "country_code", "phone", "email", "timezone", "archived_at",
    ),
    "purchases.supplier": (
        "organization_id", "company_id", "code", "name", "legal_name", "tax_identifier", "email", "phone",
        "website", "currency_id", "language_code", "lead_time_days", "minimum_order_amount", "notes", "status",
    ),
    "purchases.suppliercontact": ("supplier_id", "name", "role", "email", "phone", "is_primary"),
    "purchases.supplieraddress": (
        "supplier_id", "label", "address_line1", "address_line2", "city", "region", "postal_code", "country_code", "is_primary",
    ),
    "purchases.supplierproduct": (
        "supplier_id", "product_id", "product_variant_id", "unit_id", "currency_id", "supplier_sku",
        "lead_time_days", "minimum_quantity", "last_unit_price", "is_preferred",
    ),
    "purchases.purchaserequest": (
        "organization_id", "company_id", "establishment_id", "warehouse_id", "order_id", "number", "status",
        "needed_by", "notes", "transition_reason", "created_by_id", "approved_by_id", "submitted_at",
        "approved_at", "rejected_at", "cancelled_at",
    ),
    "purchases.purchaserequestline": (
        "purchase_request_id", "product_id", "product_variant_id", "unit_id", "quantity",
        "need_reference_type", "need_reference_id", "notes",
    ),
    "purchases.requestforquotation": (
        "organization_id", "company_id", "purchase_request_id", "number", "currency_id", "status", "due_date",
        "notes", "transition_reason", "created_by_id", "sent_at", "closed_at", "cancelled_at",
    ),
    "purchases.rfqsupplier": ("rfq_id", "supplier_id", "invited_at"),
    "purchases.supplierquotation": (
        "rfq_id", "supplier_id", "quote_number", "status", "quoted_at", "valid_until", "notes",
    ),
    "purchases.supplierquotationline": (
        "quotation_id", "product_id", "product_variant_id", "unit_id", "quantity", "unit_price", "lead_time_days",
    ),
    "purchases.purchaseorder": (
        "organization_id", "company_id", "warehouse_id", "supplier_id", "purchase_request_id", "rfq_id",
        "quotation_id", "currency_id", "number", "status", "notes", "transition_reason", "created_by_id",
        "approved_by_id", "submitted_at", "approved_at", "ordered_at", "cancelled_at",
    ),
    "purchases.purchaseorderline": (
        "purchase_order_id", "product_id", "product_variant_id", "unit_id", "quantity", "unit_price",
        "expected_date", "received_quantity",
    ),
}


def _json_safe(value):
    if isinstance(value, (UUID, datetime, date, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def audit_snapshot(instance: Model | None) -> dict | None:
    if instance is None:
        return None
    model_label = instance._meta.label_lower
    fields = SAFE_FIELDS.get(model_label, ())
    snapshot = {field: _json_safe(getattr(instance, field)) for field in fields}
    if model_label == "authorization.role":
        snapshot["permission_codes"] = list(instance.permissions.order_by("code").values_list("code", flat=True))
    elif model_label == "authorization.accessgroup":
        snapshot["member_ids"] = [str(member_id) for member_id in instance.members.order_by("id").values_list("id", flat=True)]
    return snapshot


def _scope_from_object(instance):
    company_id = None
    establishment_id = None
    if instance is None:
        return company_id, establishment_id
    model_label = instance._meta.label_lower
    if model_label == "customers.customer":
        company_id = instance.company_id
        establishment_id = instance.establishment_id
    elif model_label == "organizations.company":
        company_id = instance.id
    elif model_label == "organizations.establishment":
        company_id = instance.company_id
        establishment_id = instance.id
    elif model_label == "authorization.accessgrant":
        company_id = instance.company_id
        establishment_id = instance.establishment_id
    elif model_label in {"purchases.supplier", "purchases.purchaserequest", "purchases.requestforquotation", "purchases.purchaseorder"}:
        company_id = instance.company_id
        establishment_id = getattr(instance, "establishment_id", None)
    elif model_label in {"purchases.suppliercontact", "purchases.supplieraddress", "purchases.supplierproduct"}:
        company_id = instance.supplier.company_id
    elif model_label == "purchases.purchaserequestline":
        company_id = instance.purchase_request.company_id
        establishment_id = instance.purchase_request.establishment_id
    elif model_label in {"purchases.rfqsupplier", "purchases.supplierquotation"}:
        company_id = instance.rfq.company_id
    elif model_label == "purchases.supplierquotationline":
        company_id = instance.quotation.rfq.company_id
    elif model_label == "purchases.purchaseorderline":
        company_id = instance.purchase_order.company_id
    return company_id, establishment_id


def record_audit_event(
    *, organization, action: str, object_instance=None, object_type: str = "", object_id: str = "",
    object_label: str = "", actor=None, result: str = AuditEvent.Result.SUCCESS, before=None, after=None,
    company_id=None, establishment_id=None, request=None, metadata=None,
) -> AuditEvent:
    inferred_company_id, inferred_establishment_id = _scope_from_object(object_instance)
    company_id = company_id or inferred_company_id
    establishment_id = establishment_id or inferred_establishment_id
    if object_instance is not None:
        object_type = object_type or object_instance._meta.label_lower
        object_id = object_id or str(object_instance.pk)
        object_label = object_label or str(object_instance)
    request_id = ""
    ip_address = None
    user_agent = ""
    if request is not None:
        request_id = request.headers.get("X-Request-ID", "")[:128]
        ip_address = request.META.get("REMOTE_ADDR") or None
        user_agent = request.headers.get("User-Agent", "")[:512]
    return AuditEvent.objects.create(
        organization=organization,
        company_id=company_id,
        establishment_id=establishment_id,
        actor_id=getattr(actor, "id", None),
        actor_login=getattr(actor, "username", "")[:150] if actor else "",
        action=action[:160],
        object_type=object_type[:160],
        object_id=str(object_id)[:160],
        object_label=object_label[:255],
        result=result,
        before=_json_safe(before),
        after=_json_safe(after),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=_json_safe(metadata or {}),
    )
