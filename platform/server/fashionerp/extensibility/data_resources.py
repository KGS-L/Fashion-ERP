from dataclasses import dataclass
from typing import Callable

from django.db import models

from fashionerp.authorization.services import (
    authorized_company_ids,
    authorized_establishment_ids,
)
from fashionerp.catalog.models import Product
from fashionerp.catalog.serializers import ProductSerializer
from fashionerp.customers.models import Customer
from fashionerp.customers.serializers import CustomerSerializer

from .registry import get_model_manifest, replace_model_manifest


@dataclass(frozen=True, slots=True)
class DataResourceAdapter:
    model_key: str
    serializer_class: type
    queryset_factory: Callable
    import_fields: tuple[str, ...]
    export_fields: tuple[str, ...]
    identity_fields: tuple[str, ...]

    @property
    def manifest(self):
        return get_model_manifest(self.model_key)

    def queryset(self, user, permission_code):
        return self.queryset_factory(user, permission_code)


_RESOURCES: dict[str, DataResourceAdapter] = {}
_REGISTERED = False


def register_data_resource(adapter: DataResourceAdapter) -> DataResourceAdapter:
    if adapter.model_key in _RESOURCES and _RESOURCES[adapter.model_key] != adapter:
        raise ValueError(f"Data resource already registered: {adapter.model_key}")
    _RESOURCES[adapter.model_key] = adapter
    replace_model_manifest(adapter.model_key, importable=True, exportable=True)
    return adapter


def get_data_resource(model_key: str) -> DataResourceAdapter:
    try:
        return _RESOURCES[model_key]
    except KeyError as exc:
        raise LookupError(f"Resource does not support generic import/export: {model_key}") from exc


def _customer_queryset(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    establishment_ids = authorized_establishment_ids(user, permission_code)
    if not company_ids and not establishment_ids:
        return Customer.objects.none()
    return Customer.objects.filter(organization_id=user.organization_id).filter(
        models.Q(company_id__in=company_ids)
        | models.Q(establishment_id__in=establishment_ids)
    ).select_related("company", "establishment", "preferred_currency")


def _product_queryset(user, permission_code):
    company_ids = authorized_company_ids(user, permission_code)
    if not company_ids:
        return Product.objects.none()
    return Product.objects.filter(organization_id=user.organization_id).filter(
        models.Q(company__isnull=True) | models.Q(company_id__in=company_ids)
    ).select_related("company", "unit")


def register_default_data_resources() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    register_data_resource(
        DataResourceAdapter(
            model_key="customers.customer",
            serializer_class=CustomerSerializer,
            queryset_factory=_customer_queryset,
            import_fields=(
                "company_id",
                "establishment_id",
                "customer_type",
                "code",
                "display_name",
                "first_name",
                "last_name",
                "legal_name",
                "email",
                "phone",
                "language_code",
                "preferred_currency_id",
                "preferences",
                "notes",
            ),
            export_fields=(
                "id",
                "company_id",
                "establishment_id",
                "customer_type",
                "code",
                "display_name",
                "first_name",
                "last_name",
                "legal_name",
                "email",
                "phone",
                "language_code",
                "preferred_currency_id",
                "preferences",
                "notes",
                "status",
                "created_at",
                "updated_at",
            ),
            identity_fields=("company_id", "code"),
        )
    )
    register_data_resource(
        DataResourceAdapter(
            model_key="catalog.product",
            serializer_class=ProductSerializer,
            queryset_factory=_product_queryset,
            import_fields=(
                "company_id",
                "code",
                "name",
                "description",
                "product_type",
                "unit_id",
                "fashion_metadata",
                "is_active",
                "is_internal_published",
                "commercial_status",
                "list_price",
            ),
            export_fields=(
                "id",
                "company_id",
                "code",
                "name",
                "description",
                "product_type",
                "unit_id",
                "fashion_metadata",
                "is_active",
                "is_internal_published",
                "commercial_status",
                "list_price",
                "created_at",
                "updated_at",
            ),
            identity_fields=("code",),
        )
    )
    _REGISTERED = True
