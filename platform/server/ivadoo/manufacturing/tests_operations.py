from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.audit.models import AuditEvent
from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import FashionModel, Product
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.inventory.models import Warehouse
from ivadoo.organizations.models import Company, Organization

from .models import (
    BillOfMaterials,
    BillOfMaterialsLine,
    ManufacturingOperation,
    ManufacturingOperationTransition,
    ManufacturingOrder,
)


class ManufacturingOperationApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Operation Org", slug="operation-org"
        )
        self.company = Company.objects.create(
            organization=self.organization,
            name="Operation Company",
            code="operation-company",
        )
        self.unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="m-op",
            name="Meter",
            symbol="m",
            category="length",
            ratio_to_base=Decimal("1"),
            rounding=Decimal("0.01"),
        )
        self.fabric = Product.objects.create(
            organization=self.organization,
            company=self.company,
            code="fabric-op",
            name="Operation fabric",
            product_type=Product.ProductType.FABRIC,
            unit=self.unit,
        )
        self.fashion_model = FashionModel.objects.create(
            organization=self.organization,
            company=self.company,
            code="model-op",
            name="Operation model",
        )
        self.warehouse = Warehouse.objects.create(
            organization=self.organization,
            company=self.company,
            code="warehouse-op",
            name="Operation warehouse",
        )
        self.user = User.objects.create_user(
            username="operation.manager",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        permission_codes = (
            "manufacturing.order.view",
            "manufacturing.order.manage",
            "manufacturing.order.transition",
            "manufacturing.work_center.view",
            "manufacturing.work_center.manage",
            "manufacturing.operation.view",
            "manufacturing.operation.manage",
            "manufacturing.operation.transition",
            "manufacturing.operation.override_sequence",
        )
        role = Role.objects.create(
            organization=self.organization,
            code="operation-manager",
            name="Operation manager",
            is_active=True,
        )
        role.permissions.set(Permission.objects.filter(code__in=permission_codes))
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.bom = BillOfMaterials.objects.create(
            organization=self.organization,
            company=self.company,
            fashion_model=self.fashion_model,
            code="BOM-OP",
            version=1,
            status=BillOfMaterials.Status.ACTIVE,
            batch_quantity=Decimal("1"),
            created_by=self.user,
        )
        BillOfMaterialsLine.objects.create(
            bom=self.bom,
            product=self.fabric,
            quantity=Decimal("1.5"),
            unit=self.unit,
            position=1,
        )
        self.manufacturing_order = ManufacturingOrder.objects.create(
            organization=self.organization,
            company=self.company,
            warehouse=self.warehouse,
            bom=self.bom,
            number="MO-OPS-1",
            planned_quantity=Decimal("2"),
            created_by=self.user,
        )

    def create_work_center(self):
        response = self.client.post(
            "/api/v1/manufacturing/work-centers/",
            {
                "company_id": str(self.company.id),
                "code": "sewing-line-1",
                "name": "Sewing line 1",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data

    def create_operation(self, *, position, operation_type, name, work_center_id=None):
        payload = {
            "operation_type": operation_type,
            "name": name,
            "position": position,
            "planned_minutes": 30,
            "planned_quantity": "2.0000",
        }
        if work_center_id:
            payload["work_center_id"] = work_center_id
        response = self.client.post(
            f"/api/v1/manufacturing/orders/{self.manufacturing_order.id}/operations/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data

    def start_manufacturing_order(self):
        ready = self.client.post(
            f"/api/v1/manufacturing/orders/{self.manufacturing_order.id}/actions/",
            {"action": "ready"},
            format="json",
        )
        self.assertEqual(ready.status_code, status.HTTP_200_OK, ready.data)
        started = self.client.post(
            f"/api/v1/manufacturing/orders/{self.manufacturing_order.id}/actions/",
            {"action": "start"},
            format="json",
        )
        self.assertEqual(started.status_code, status.HTTP_200_OK, started.data)

    def action(self, operation_id, payload):
        return self.client.post(
            f"/api/v1/manufacturing/operations/{operation_id}/actions/",
            payload,
            format="json",
        )

    def test_operations_execute_in_sequence_and_record_history(self):
        work_center = self.create_work_center()
        cutting = self.create_operation(
            position=10,
            operation_type="cutting",
            name="Cutting",
        )
        sewing = self.create_operation(
            position=20,
            operation_type="sewing",
            name="Sewing",
            work_center_id=work_center["id"],
        )
        self.start_manufacturing_order()

        blocked = self.action(sewing["id"], {"action": "start"})
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)

        started = self.action(cutting["id"], {"action": "start"})
        self.assertEqual(started.status_code, status.HTTP_200_OK, started.data)
        completed = self.action(
            cutting["id"],
            {
                "action": "complete",
                "processed_quantity": "2.0000",
                "actual_minutes": 28,
            },
        )
        self.assertEqual(completed.status_code, status.HTTP_200_OK, completed.data)
        self.assertEqual(completed.data["status"], ManufacturingOperation.Status.DONE)

        second_started = self.action(sewing["id"], {"action": "start"})
        self.assertEqual(second_started.status_code, status.HTTP_200_OK, second_started.data)
        self.assertEqual(
            ManufacturingOperationTransition.objects.filter(operation_id=cutting["id"]).count(),
            2,
        )
        self.assertTrue(
            AuditEvent.objects.filter(action="manufacturing.operation.complete").exists()
        )

    def test_sequence_override_requires_reason_and_is_audited(self):
        self.create_operation(position=10, operation_type="cutting", name="Cutting")
        sewing = self.create_operation(position=20, operation_type="sewing", name="Sewing")
        self.start_manufacturing_order()

        no_reason = self.action(
            sewing["id"],
            {"action": "start", "override_sequence": True},
        )
        self.assertEqual(no_reason.status_code, status.HTTP_400_BAD_REQUEST)

        override = self.action(
            sewing["id"],
            {
                "action": "start",
                "override_sequence": True,
                "reason": "Approved recovery sequence after machine outage",
            },
        )
        self.assertEqual(override.status_code, status.HTTP_200_OK, override.data)
        history = ManufacturingOperationTransition.objects.get(operation_id=sewing["id"])
        self.assertTrue(history.sequence_override)
        self.assertTrue(history.reason)

    def test_rework_is_explicit_and_actual_time_is_cumulative(self):
        finishing = self.create_operation(
            position=10,
            operation_type="finishing",
            name="Finishing",
        )
        self.start_manufacturing_order()
        self.assertEqual(
            self.action(finishing["id"], {"action": "start"}).status_code,
            status.HTTP_200_OK,
        )
        first_done = self.action(
            finishing["id"],
            {
                "action": "complete",
                "processed_quantity": "2.0000",
                "actual_minutes": 20,
            },
        )
        self.assertEqual(first_done.status_code, status.HTTP_200_OK, first_done.data)
        rework = self.action(
            finishing["id"],
            {"action": "rework", "reason": "Finishing defect to correct"},
        )
        self.assertEqual(rework.status_code, status.HTTP_200_OK, rework.data)
        self.assertEqual(rework.data["rework_count"], 1)
        self.assertEqual(
            self.action(finishing["id"], {"action": "start"}).status_code,
            status.HTTP_200_OK,
        )
        second_done = self.action(
            finishing["id"],
            {
                "action": "complete",
                "processed_quantity": "2.0000",
                "actual_minutes": 12,
            },
        )
        self.assertEqual(second_done.status_code, status.HTTP_200_OK, second_done.data)
        self.assertEqual(second_done.data["actual_minutes"], 32)
        self.assertEqual(second_done.data["rework_count"], 1)
