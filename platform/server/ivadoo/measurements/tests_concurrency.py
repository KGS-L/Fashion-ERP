from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from ivadoo.customers.models import Customer
from ivadoo.identity.models import User
from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.organizations.models import Company, Organization

from .models import MeasurementDefinition, MeasurementSet
from .serializers import MeasurementSetSerializer


class MeasurementVersionConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.organization = Organization.objects.create(
            name="Measurement concurrency",
            slug="measurement-concurrency",
        )
        self.company = Company.objects.create(
            organization=self.organization,
            name="Maison",
            code="measurement-concurrency-maison",
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            company=self.company,
            code="C-CONCURRENCY",
            display_name="Concurrent client",
        )
        self.user = User.objects.create_user(
            username="measurement.concurrent",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        self.unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="cm-measurement-concurrency",
            name="Centimeter",
            symbol="cm",
            category="length",
            ratio_to_base=Decimal("0.01"),
            rounding=Decimal("0.1"),
        )
        self.definition = MeasurementDefinition.objects.create(
            organization=self.organization,
            code="chest-measurement-concurrency",
            name="Chest",
            unit=self.unit,
        )

    def payload(self, index):
        return {
            "company_id": str(self.company.id),
            "customer_id": str(self.customer.id),
            "measured_at": timezone.now().isoformat(),
            "notes": f"Concurrent capture {index}",
            "values": [
                {
                    "definition_id": str(self.definition.id),
                    "value": str(Decimal("90") + index),
                    "tolerance": "1.0000",
                    "note": "",
                }
            ],
        }

    def test_concurrent_measurements_allocate_distinct_monotonic_versions(self):
        if connection.vendor != "postgresql":
            self.skipTest("This regression test requires PostgreSQL row locking.")

        workers = 4
        barrier = Barrier(workers)
        organization_id = self.organization.id
        user_id = self.user.id

        def create_measurement(index):
            close_old_connections()
            try:
                serializer = MeasurementSetSerializer(data=self.payload(index))
                serializer.is_valid(raise_exception=True)
                barrier.wait(timeout=10)
                measurement_set = serializer.save(
                    organization=Organization.objects.get(pk=organization_id),
                    created_by=User.objects.get(pk=user_id),
                )
                return measurement_set.version
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            versions = list(executor.map(create_measurement, range(workers)))

        self.assertEqual(sorted(versions), [1, 2, 3, 4])
        self.assertEqual(
            list(
                MeasurementSet.objects.filter(customer=self.customer)
                .order_by("version")
                .values_list("version", flat=True)
            ),
            [1, 2, 3, 4],
        )
