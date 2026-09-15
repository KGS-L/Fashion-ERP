from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import FashionModel, Product
from ivadoo.customers.models import Customer
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.inventory.models import Warehouse
from ivadoo.manufacturing.models import BillOfMaterials, ManufacturingOperation, ManufacturingOrder
from ivadoo.measurements.models import MeasurementDefinition, MeasurementSet, MeasurementValue
from ivadoo.organizations.models import Company, Organization

from .models import AlterationRequest, Order, OrderLine


class FittingAlterationFlowTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Fittings", slug="fittings")
        self.company = Company.objects.create(organization=self.organization, name="Maison", code="fit-maison")
        self.customer = Customer.objects.create(organization=self.organization, company=self.company, code="FIT-C1", display_name="Client")
        self.user = User.objects.create_user(username="fitting.manager", password="Strong-Test-Password-42!", organization=self.organization)
        role = Role.objects.create(organization=self.organization, code="fitting-manager", name="Fitting manager", is_active=True)
        role.permissions.set(Permission.objects.filter(code__in=(
            "fashion.sale.view", "fashion.sale.manage", "fashion.fitting.view", "fashion.fitting.manage",
            "fashion.alteration.manage", "fashion.customer_validation.manage", "manufacturing.operation.transition",
        )))
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.unit = UnitOfMeasure.objects.create(
            organization=self.organization, code="cm-fit", name="Centimeter", symbol="cm", category="length",
            ratio_to_base=Decimal("0.01"), rounding=Decimal("0.1"),
        )
        definition = MeasurementDefinition.objects.create(organization=self.organization, code="waist-fit", name="Waist", unit=self.unit)
        measurement_set = MeasurementSet.objects.create(
            organization=self.organization, company=self.company, customer=self.customer, version=1,
            measured_at=timezone.now(), created_by=self.user,
        )
        MeasurementValue.objects.create(measurement_set=measurement_set, definition=definition, value=Decimal("78"))
        self.order = Order.objects.create(organization=self.organization, company=self.company, customer=self.customer, number="FIT-O-1")
        self.line = OrderLine.objects.create(
            order=self.order, description="Custom dress", quantity=Decimal("1"), unit_price=Decimal("75000"), measurement_set=measurement_set,
        )
        confirm = self.client.post(f"/api/v1/sales/orders/{self.order.id}/actions/confirm/")
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        self.line.refresh_from_db()
        self.snapshot = self.line.measurement_snapshot.copy()

    def _fitting(self):
        return self.client.post(
            "/api/v1/sales/fittings/",
            {"order_id": str(self.order.id), "scheduled_at": "2026-09-16T10:00:00Z", "requires_customer_validation": True},
            format="json",
        )

    def test_alteration_then_new_fitting_and_customer_validation_unlock_delivery(self):
        first = self._fitting()
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        alteration = self.client.post(
            "/api/v1/sales/alterations/",
            {
                "fitting_id": first.data["id"], "order_line_id": str(self.line.id), "reason": "Waist too loose",
                "adjustment_notes": "Take in waist by approximately 2 cm; keep original measurement snapshot unchanged.", "priority": "high",
            },
            format="json",
        )
        self.assertEqual(alteration.status_code, status.HTTP_201_CREATED)
        completed_first = self.client.post(
            f"/api/v1/sales/fittings/{first.data['id']}/actions/complete/",
            {"result": "alteration_required", "notes": "Client requested waist adjustment"}, format="json",
        )
        self.assertEqual(completed_first.status_code, status.HTTP_200_OK)
        readiness = self.client.get(f"/api/v1/sales/orders/{self.order.id}/delivery-readiness/")
        self.assertFalse(readiness.data["deliverable"])
        self.assertIn("open_alterations", readiness.data["blockers"])

        started = self.client.post(f"/api/v1/sales/alterations/{alteration.data['id']}/actions/start/", {}, format="json")
        self.assertEqual(started.status_code, status.HTTP_200_OK)
        done = self.client.post(f"/api/v1/sales/alterations/{alteration.data['id']}/actions/complete/", {}, format="json")
        self.assertEqual(done.status_code, status.HTTP_200_OK)

        second = self._fitting()
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        second_done = self.client.post(
            f"/api/v1/sales/fittings/{second.data['id']}/actions/complete/", {"result": "fit_ok"}, format="json"
        )
        self.assertEqual(second_done.status_code, status.HTTP_200_OK)
        validation = self.client.post(
            "/api/v1/sales/customer-validations/",
            {"fitting_id": second.data["id"], "decision": "approved", "customer_name": "Client", "notes": "Fit approved"},
            format="json",
        )
        self.assertEqual(validation.status_code, status.HTTP_201_CREATED)
        readiness = self.client.get(f"/api/v1/sales/orders/{self.order.id}/delivery-readiness/")
        self.assertTrue(readiness.data["deliverable"])
        self.assertEqual(readiness.data["blockers"], [])
        self.line.refresh_from_db()
        self.assertEqual(self.line.measurement_snapshot, self.snapshot)

    def test_alteration_can_reopen_linked_completed_operation_for_rework(self):
        piece = UnitOfMeasure.objects.create(
            organization=self.organization, code="pc-fit", name="Piece", symbol="pc", category="unit", ratio_to_base=Decimal("1"), rounding=Decimal("1")
        )
        finished = Product.objects.create(
            organization=self.organization, company=self.company, code="fit-finished", name="Finished garment",
            product_type=Product.ProductType.FINISHED_GOOD, unit=piece,
        )
        fashion_model = FashionModel.objects.create(organization=self.organization, company=self.company, code="fit-model", name="Fit model")
        warehouse = Warehouse.objects.create(organization=self.organization, company=self.company, code="fit-wh", name="Fit warehouse")
        bom = BillOfMaterials.objects.create(
            organization=self.organization, company=self.company, fashion_model=fashion_model, output_product=finished,
            code="BOM-FIT", version=1, status=BillOfMaterials.Status.ACTIVE, batch_quantity=Decimal("1"), created_by=self.user,
        )
        mo = ManufacturingOrder.objects.create(
            organization=self.organization, company=self.company, warehouse=warehouse, order=self.order, bom=bom,
            number="MO-FIT-1", status=ManufacturingOrder.Status.IN_PROGRESS, planned_quantity=Decimal("1"), created_by=self.user,
        )
        operation = ManufacturingOperation.objects.create(
            organization=self.organization, company=self.company, manufacturing_order=mo,
            operation_type=ManufacturingOperation.OperationType.SEWING, name="Sewing", position=1,
            status=ManufacturingOperation.Status.DONE, planned_quantity=Decimal("1"), processed_quantity=Decimal("1"), created_by=self.user,
        )
        fitting = self._fitting()
        alteration = self.client.post(
            "/api/v1/sales/alterations/",
            {
                "fitting_id": fitting.data["id"], "reason": "Sleeve adjustment",
                "manufacturing_order_id": str(mo.id), "manufacturing_operation_id": str(operation.id),
            }, format="json",
        )
        self.assertEqual(alteration.status_code, status.HTTP_201_CREATED)
        response = self.client.post(
            f"/api/v1/sales/alterations/{alteration.data['id']}/actions/start/", {"reopen_operation": True}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        operation.refresh_from_db()
        self.assertEqual(operation.status, ManufacturingOperation.Status.REWORK)
        self.assertEqual(operation.rework_count, 1)
        self.assertEqual(AlterationRequest.objects.get(id=alteration.data["id"]).status, AlterationRequest.Status.IN_PROGRESS)

    def test_user_without_fitting_scope_sees_no_fittings(self):
        self.assertEqual(self._fitting().status_code, status.HTTP_201_CREATED)
        outsider = User.objects.create_user(username="fitting.outsider", password="Strong-Test-Password-42!", organization=self.organization)
        _, token = create_api_session(user=outsider)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get("/api/v1/sales/fittings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
