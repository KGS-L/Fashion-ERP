import getpass
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fashionerp.organizations.services import provision_local_organization


class Command(BaseCommand):
    help = "Bootstrap the local FashionERP Data Plane organization and initial user."

    def add_arguments(self, parser):
        parser.add_argument("--organization-name", required=True)
        parser.add_argument("--organization-slug", required=True)
        parser.add_argument("--login", required=True)
        parser.add_argument("--email", default="")

    @transaction.atomic
    def handle(self, *args, **options):
        user_model = get_user_model()

        if user_model.objects.exists():
            raise CommandError(
                "The Data Plane already contains users; refusing bootstrap."
            )

        password = os.getenv("FASHIONERP_BOOTSTRAP_PASSWORD")
        if not password:
            password = getpass.getpass("Initial user password: ")

        if not password:
            raise CommandError("A non-empty bootstrap password is required.")

        try:
            organization = provision_local_organization(
                name=options["organization_name"],
                slug=options["organization_slug"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        user = user_model.objects.create_user(
            username=options["login"],
            password=password,
            email=options["email"],
            organization=organization,
            is_active=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Bootstrapped organization {organization.id} and user {user.id}."
            )
        )
