from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from fashionerp.authorization.models import AccessGrant, Permission, Role
from fashionerp.authorization.services import FOUNDATION_PERMISSIONS
from fashionerp.internationalization.models import Currency, UnitOfMeasure
from fashionerp.organizations.models import Company, Establishment, Organization


REFERENCE_PASSWORD = "Foundation-Test-Password-42!"


class Command(BaseCommand):
    help = (
        "Create deterministic non-production Foundation reference data "
        "for validation and integration tests."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="Django database alias to seed.",
        )
        parser.add_argument(
            "--profile",
            choices=("pilot", "isolation"),
            default="pilot",
            help="Reference profile to create.",
        )

    def handle(self, *args, **options):
        alias = options["database"]
        profile = options["profile"]

        if alias not in connections:
            raise CommandError(f"Unknown database alias: {alias}")

        if profile == "pilot":
            summary = self._seed_pilot(alias)
        else:
            summary = self._seed_isolation(alias)

        self.stdout.write(
            self.style.SUCCESS(
                f"Foundation reference profile '{profile}' ready on "
                f"database '{alias}': {summary}"
            )
        )

    @transaction.atomic
    def _seed_pilot(self, alias):
        organization = self._organization(
            alias,
            name="Foundation Pilot Organization",
            slug="foundation-pilot",
        )
        currency, _ = Currency.objects.using(alias).update_or_create(
            code="XTS",
            defaults={
                "name": "Foundation Test Currency",
                "symbol": "T",
                "decimal_places": 2,
                "rounding": "0.01000000",
                "is_active": True,
            },
        )
        company, _ = Company.objects.using(alias).update_or_create(
            organization=organization,
            code="pilot-company",
            defaults={
                "name": "Foundation Pilot Company",
                "legal_name": "Foundation Pilot Company",
                "country_code": "BF",
                "language_code": "fr",
                "functional_currency": currency,
                "status": Company.Status.ACTIVE,
            },
        )
        workshop, _ = Establishment.objects.using(alias).update_or_create(
            company=company,
            code="pilot-workshop",
            defaults={
                "name": "Pilot Workshop",
                "site_type": Establishment.SiteType.WORKSHOP,
                "city": "Ouagadougou",
                "country_code": "BF",
                "timezone": "Africa/Ouagadougou",
                "status": Establishment.Status.ACTIVE,
            },
        )
        store, _ = Establishment.objects.using(alias).update_or_create(
            company=company,
            code="pilot-store",
            defaults={
                "name": "Pilot Store",
                "site_type": Establishment.SiteType.STORE,
                "city": "Ouagadougou",
                "country_code": "BF",
                "timezone": "Africa/Ouagadougou",
                "status": Establishment.Status.ACTIVE,
            },
        )
        UnitOfMeasure.objects.using(alias).update_or_create(
            organization=organization,
            code="metre",
            defaults={
                "name": "Metre",
                "symbol": "m",
                "category": "length",
                "ratio_to_base": "1.000000000000",
                "rounding": "0.00100000",
                "is_active": True,
            },
        )

        permissions = self._permissions(alias)
        admin_role, _ = Role.objects.using(alias).update_or_create(
            organization=organization,
            code="organization-admin",
            defaults={
                "name": "Organization administrator",
                "description": "Reference full-access administrator.",
                "is_full_access": True,
                "is_system": True,
                "is_active": True,
            },
        )
        reader_role, _ = Role.objects.using(alias).update_or_create(
            organization=organization,
            code="reference-reader",
            defaults={
                "name": "Reference reader",
                "description": "Read-only reference role for scope tests.",
                "is_full_access": False,
                "is_system": False,
                "is_active": True,
            },
        )
        reader_role.permissions.set(
            [
                permissions["foundation.company.view"],
                permissions["foundation.establishment.view"],
            ]
        )

        admin = self._user(
            alias,
            organization,
            username="foundation.admin",
            email="foundation.admin@example.test",
            language_code="fr",
        )
        company_reader = self._user(
            alias,
            organization,
            username="company.reader",
            email="company.reader@example.test",
            language_code="en",
        )
        workshop_reader = self._user(
            alias,
            organization,
            username="workshop.reader",
            email="workshop.reader@example.test",
            language_code="pt",
        )

        self._grant(alias, role=admin_role, user=admin)
        self._grant(
            alias,
            role=reader_role,
            user=company_reader,
            company=company,
        )
        self._grant(
            alias,
            role=reader_role,
            user=workshop_reader,
            establishment=workshop,
        )

        return (
            f"organization={organization.slug}, company={company.code}, "
            f"establishments={workshop.code},{store.code}, users=3"
        )

    @transaction.atomic
    def _seed_isolation(self, alias):
        organization = self._organization(
            alias,
            name="Foundation Isolation Organization",
            slug="foundation-isolation",
        )
        company, _ = Company.objects.using(alias).update_or_create(
            organization=organization,
            code="isolation-company",
            defaults={
                "name": "Isolation Company",
                "country_code": "BF",
                "language_code": "fr",
                "status": Company.Status.ACTIVE,
            },
        )
        Establishment.objects.using(alias).update_or_create(
            company=company,
            code="isolation-site",
            defaults={
                "name": "Isolation Site",
                "site_type": Establishment.SiteType.WORKSHOP,
                "timezone": "UTC",
                "status": Establishment.Status.ACTIVE,
            },
        )
        self._user(
            alias,
            organization,
            username="isolation.user",
            email="isolation.user@example.test",
            language_code="fr",
        )
        return f"organization={organization.slug}, company={company.code}"

    def _organization(self, alias, *, name, slug):
        existing = Organization.objects.using(alias).first()
        if existing and existing.slug != slug:
            raise CommandError(
                f"Database '{alias}' is already bound to organization "
                f"'{existing.slug}'."
            )
        organization, _ = Organization.objects.using(alias).update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "status": Organization.Status.ACTIVE,
            },
        )
        return organization

    def _permissions(self, alias):
        result = {}
        for code, module, action, name in FOUNDATION_PERMISSIONS:
            permission, _ = Permission.objects.using(alias).update_or_create(
                code=code,
                defaults={
                    "module": module,
                    "action": action,
                    "name": name,
                },
            )
            result[code] = permission
        return result

    def _user(
        self,
        alias,
        organization,
        *,
        username,
        email,
        language_code,
    ):
        manager = get_user_model().objects.db_manager(alias)
        user = manager.filter(username=username).first()
        if user is None:
            user = manager.create_user(
                username=username,
                password=REFERENCE_PASSWORD,
                email=email,
                organization=organization,
                language_code=language_code,
            )
        else:
            user.email = email
            user.organization = organization
            user.language_code = language_code
            user.is_active = True
            user.set_password(REFERENCE_PASSWORD)
            user.save(
                using=alias,
                update_fields=(
                    "email",
                    "organization",
                    "language_code",
                    "is_active",
                    "password",
                ),
            )
        return user

    def _grant(
        self,
        alias,
        *,
        role,
        user,
        company=None,
        establishment=None,
    ):
        filters = {
            "role": role,
            "user": user,
            "group__isnull": True,
            "company": company,
            "establishment": establishment,
            "revoked_at__isnull": True,
        }
        grant = AccessGrant.objects.using(alias).filter(**filters).first()
        if grant is None:
            grant = AccessGrant.objects.using(alias).create(
                role=role,
                user=user,
                company=company,
                establishment=establishment,
            )
        return grant
