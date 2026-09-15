from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Organization


@transaction.atomic
def provision_local_organization(*, name: str, slug: str) -> Organization:
    if Organization.objects.exists():
        raise ValidationError(
            "This ERP Data Plane database is already bound to an organization."
        )

    return Organization.objects.create(
        name=name,
        slug=slug,
        status=Organization.Status.ACTIVE,
    )
