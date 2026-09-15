from decimal import Decimal

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import FashionModel, Product
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.inventory.models import Warehouse
from ivadoo.manufacturing.models import BillOfMaterials, ManufacturingOperation, ManufacturingOrder
from ivadoo.manufacturing.operation_services import transition_operation
from ivadoo.organizations.models import Company, Organization

from .models import QualityCriterion, QualityInspection, QualityRework
from .services import assert_quality_gate_passed, complete_inspection


class QualityApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Quality", slug="quality")
        self.company = Company.objects.create(organization=self.organization, name="Maison", code="quality-maison")
        self.user = User.objects.create_user(username="quality.manager", password="Strong-Test-Password-42!", organization=self.organization)
        role = Role.objects.create(organization=self.organization, code="quality-manager", name="Quality manager", is_active=True)
        role.permissions.set(Permission.objects.filter(code__in=(
            "quality.inspection.view", "quality.inspection.manage", "quality.inspection.complete", "quality.rework.manage", "quality.metrics.view"
        )))
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.unit = UnitOfMeasure.objects.create(organization=self.organization, code="pc-quality", name="Piece", symbol="pc", category="unit", ratio_to_base=Decimal("1"), rounding=Decimal("1"))
        self.finished = Product.objects.create(organization=self.organization, company=self.company, code="finished-quality", name="Finished", product_type=Product.ProductType.FINISHED_GOOD, unit=self.unit)
        self.model = FashionModel.objects.create(organization=self.organization, company=self.company, code="quality-model", name="Quality model")
        self.warehouse = Warehouse.objects.create(organization=self.organization, company=self.company, code="quality-wh", name="Quality warehouse")
        self.bom = BillOfMaterials.objects.create(
            organization=self.organization, company=self.company, fashion_model=self.model, output_product=self.finished,
            code="BOM-QUALITY", version=1, status=BillOfMaterials.Status.ACTIVE, batch_quantity=Decimal("1"), created_by=self.user
        )
        self.mo = ManufacturingOrder.objects.create(
            organization=self.organization, company=self.company, warehouse=self.warehouse, bom=self.bom,
            number="MO-QUALITY-1", planned_quantity=Decimal("1"), created_by=self.user
        )

    def _create_inspection(self, **overrides):
        payload = {
            "company_id": str(self.company.id), "inspection_type": "in_process", "manufacturing_order_id": str(self.mo.id),
            "blocking": True, "criteria": [{"code": "seam", "label": "Seam", "result": "pass", "position": 1}], "defects": [],
        }
        payload.update(overrides)
        return self.client.post("/api/v1/quality/inspections/", payload, format="json")

    def test_rework_reinspection_and_gate_are_traceable(self):
        created = self._create_inspection(
            criteria=[{"code": "seam", "label": "Seam", "result": "fail"}],
            defects=[{"code": "DEF-1", "severity": "major", "description": "Open seam", "quantity": "1", "photo_references": ["files/quality/def-1.jpg"]}],
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        inspection_id = created.data["id"]
        completed = self.client.post(
            f"/api/v1/quality/inspections/{inspection_id}/complete/",
            {"decision": "rework", "reason": "Seam failed", "rework_instructions": "Restitch seam"}, format="json",
        )
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        inspection = QualityInspection.objects.get(id=inspection_id)
        with self.assertRaisesMessage(ValidationError, "Quality gate blocked"):
            assert_quality_gate_passed(manufacturing_order=inspection.manufacturing_order)
        rework = QualityRework.objects.get(inspection=inspection)
        done = self.client.post(f"/api/v1/quality/reworks/{rework.id}/complete/", {"result_notes": "Restitched"}, format="json")
        self.assertEqual(done.status_code, status.HTTP_200_OK)
        followup = self._create_inspection(parent_inspection_id=str(inspection.id))
        self.assertEqual(followup.status_code, status.HTTP_201_CREATED)
        accepted = self.client.post(f"/api/v1/quality/inspections/{followup.data['id']}/complete/", {"decision": "accept"}, format="json")
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        latest = assert_quality_gate_passed(manufacturing_order=self.mo)
        self.assertEqual(str(latest.id), followup.data["id"])

    def test_failed_criteria_cannot_be_accepted(self):
        created = self._create_inspection(criteria=[{"code": "finish", "label": "Finish", "result": "fail"}])
        response = self.client.post(f"/api/v1/quality/inspections/{created.data['id']}/complete/", {"decision": "accept"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_blocking_operation_reject_prevents_next_operation_start(self):
        self.mo.status = ManufacturingOrder.Status.IN_PROGRESS
        self.mo.save(update_fields=("status", "updated_at"))
        first = ManufacturingOperation.objects.create(
            organization=self.organization, company=self.company, manufacturing_order=self.mo,
            operation_type=ManufacturingOperation.OperationType.CUTTING, name="Cut", position=1,
            status=ManufacturingOperation.Status.DONE, planned_quantity=Decimal("1"), processed_quantity=Decimal("1"), created_by=self.user,
        )
        second = ManufacturingOperation.objects.create(
            organization=self.organization, company=self.company, manufacturing_order=self.mo,
            operation_type=ManufacturingOperation.OperationType.SEWING, name="Sew", position=2,
            planned_quantity=Decimal("1"), created_by=self.user,
        )
        inspection = QualityInspection.objects.create(
            organization=self.organization, company=self.company, inspection_type=QualityInspection.InspectionType.IN_PROCESS,
            manufacturing_operation=first, blocking=True, created_by=self.user,
        )
        QualityCriterion.objects.create(inspection=inspection, code="cut", label="Cut quality", result=QualityCriterion.Result.FAIL)
        complete_inspection(inspection=inspection, decision=QualityInspection.Decision.REJECT, actor=self.user, reason="Cut defect")
        with self.assertRaisesMessage(ValidationError, "Quality gate blocked"):
            transition_operation(operation=second, action="start", actor=self.user)
        second.refresh_from_db()
        self.assertEqual(second.status, ManufacturingOperation.Status.PENDING)

    def test_summary_exposes_operational_quality_aggregates(self):
        created = self._create_inspection()
        self.client.post(f"/api/v1/quality/inspections/{created.data['id']}/complete/", {"decision": "accept"}, format="json")
        response = self.client.get("/api/v1/quality/summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["accepted"], 1)
        self.assertEqual(response.data["defect_count"], 0)

    def test_user_without_quality_scope_sees_no_inspections(self):
        self.assertEqual(self._create_inspection().status_code, status.HTTP_201_CREATED)
        outsider = User.objects.create_user(username="quality.outsider", password="Strong-Test-Password-42!", organization=self.organization)
        _, token = create_api_session(user=outsider)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get("/api/v1/quality/inspections/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
