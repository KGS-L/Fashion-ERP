from django.db.models import Q, QuerySet

from fashionerp.organizations.models import Company, Establishment

from .models import AccessGrant, Permission, Role


FOUNDATION_PERMISSIONS = (
    ("fashion.customer.view", "fashion", "customer.view", "View customers"),
    ("fashion.customer.manage", "fashion", "customer.manage", "Manage customers"),
    ("platform.module.view", "platform", "module.view", "View module registry"),
    ("platform.module.manage", "platform", "module.manage", "Manage module registry"),
    ("platform.customization.view", "platform", "customization.view", "View customization metadata"),
    ("platform.customization.manage", "platform", "customization.manage", "Manage customizations"),
    ("platform.data.import", "platform", "data.import", "Import authorized business data"),
    ("platform.data.export", "platform", "data.export", "Export authorized business data"),
    ("foundation.organization.view", "foundation", "organization.view", "View organization"),
    ("foundation.company.view", "foundation", "company.view", "View companies"),
    ("foundation.company.manage", "foundation", "company.manage", "Manage companies"),
    (
        "foundation.establishment.view",
        "foundation",
        "establishment.view",
        "View establishments",
    ),
    (
        "foundation.establishment.manage",
        "foundation",
        "establishment.manage",
        "Manage establishments",
    ),
    ("foundation.access.manage", "foundation", "access.manage", "Manage access"),
    ("foundation.audit.view", "foundation", "audit.view", "View audit journal"),
    ("foundation.i18n.view", "foundation", "i18n.view", "View international settings"),
    ("foundation.i18n.manage", "foundation", "i18n.manage", "Manage international settings"),
)


def ensure_foundation_permission_catalog() -> None:
    for code, module, action, name in FOUNDATION_PERMISSIONS:
        Permission.objects.update_or_create(
            code=code,
            defaults={
                "module": module,
                "action": action,
                "name": name,
            },
        )


def ensure_organization_admin_role(*, organization) -> Role:
    ensure_foundation_permission_catalog()
    role, _ = Role.objects.update_or_create(
        organization=organization,
        code="organization-admin",
        defaults={
            "name": "Organization administrator",
            "description": "Protected full-access Data Plane administrator role.",
            "is_full_access": True,
            "is_system": True,
            "is_active": True,
        },
    )
    return role


def grant_organization_admin(*, user) -> AccessGrant:
    role = ensure_organization_admin_role(organization=user.organization)
    grant = AccessGrant.objects.filter(
        user=user,
        role=role,
        company__isnull=True,
        establishment__isnull=True,
        revoked_at__isnull=True,
    ).first()
    if grant:
        return grant
    return AccessGrant.objects.create(user=user, role=role)


def active_grants_for_user(user) -> QuerySet:
    if not user or not user.is_authenticated or not user.is_active:
        return AccessGrant.objects.none()

    return (
        AccessGrant.objects.filter(
            Q(user=user)
            | Q(group__members=user, group__is_active=True),
            revoked_at__isnull=True,
            role__is_active=True,
            role__organization_id=user.organization_id,
        )
        .select_related(
            "role",
            "company",
            "establishment",
            "establishment__company",
        )
        .prefetch_related("role__permissions")
        .distinct()
    )


def _role_allows(grant: AccessGrant, permission_code: str) -> bool:
    return grant.role.is_full_access or any(
        permission.code == permission_code
        for permission in grant.role.permissions.all()
    )


def has_any_scope_permission(user, permission_code: str) -> bool:
    """Return whether the user has this permission in at least one active scope."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    return any(
        _role_allows(grant, permission_code)
        for grant in active_grants_for_user(user)
    )


def _scope_covers(
    grant: AccessGrant,
    *,
    company: Company | None = None,
    establishment: Establishment | None = None,
) -> bool:
    if grant.establishment_id:
        return bool(
            establishment
            and grant.establishment_id == establishment.id
        )

    if grant.company_id:
        target_company_id = (
            establishment.company_id if establishment else getattr(company, "id", None)
        )
        return grant.company_id == target_company_id

    return True


def has_permission(
    user,
    permission_code: str,
    *,
    company: Company | None = None,
    establishment: Establishment | None = None,
) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False

    if company and company.organization_id != user.organization_id:
        return False

    if (
        establishment
        and establishment.company.organization_id != user.organization_id
    ):
        return False

    for grant in active_grants_for_user(user):
        if _role_allows(grant, permission_code) and _scope_covers(
            grant,
            company=company,
            establishment=establishment,
        ):
            return True
    return False


def authorized_company_ids(user, permission_code: str) -> set:
    companies = Company.objects.filter(organization_id=user.organization_id)
    allowed = set()

    for grant in active_grants_for_user(user):
        if not _role_allows(grant, permission_code):
            continue
        if grant.scope_type == "organization":
            return set(companies.values_list("id", flat=True))
        if grant.company_id:
            allowed.add(grant.company_id)

    return allowed


def authorized_establishment_ids(user, permission_code: str) -> set:
    establishments = Establishment.objects.filter(
        company__organization_id=user.organization_id
    )
    allowed = set()

    for grant in active_grants_for_user(user):
        if not _role_allows(grant, permission_code):
            continue
        if grant.scope_type == "organization":
            return set(establishments.values_list("id", flat=True))
        if grant.company_id:
            allowed.update(
                establishments.filter(company_id=grant.company_id).values_list(
                    "id",
                    flat=True,
                )
            )
        elif grant.establishment_id:
            allowed.add(grant.establishment_id)

    return allowed
