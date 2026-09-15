from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from fashionerp.authorization.models import AccessGrant,Permission,Role
from fashionerp.catalog.models import FashionModel
from fashionerp.customers.models import Customer
from fashionerp.identity.models import User
from fashionerp.identity.services import create_api_session
from fashionerp.internationalization.models import Currency
from fashionerp.measurements.models import MeasurementDefinition,MeasurementSet,MeasurementValue
from fashionerp.internationalization.models import UnitOfMeasure
from fashionerp.organizations.models import Company,Organization

class FashionSalesFlowTests(APITestCase):
 def setUp(self):
  self.org=Organization.objects.create(name="Sales",slug="sales");self.company=Company.objects.create(organization=self.org,name="Maison",code="sales-maison");self.customer=Customer.objects.create(organization=self.org,company=self.company,code="C1",display_name="Client")
  self.user=User.objects.create_user(username="sales.user",password="Strong-Test-Password-42!",organization=self.org);role=Role.objects.create(organization=self.org,code="sales-manager",name="Sales manager",is_active=True);role.permissions.set(Permission.objects.filter(code__in=("fashion.sale.view","fashion.sale.manage")));AccessGrant.objects.create(user=self.user,role=role,company=self.company);_,token=create_api_session(user=self.user);self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
  self.currency=Currency.objects.create(code="XOF",name="CFA Franc",symbol="F",decimal_places=0,rounding=Decimal("1"))
  self.unit=UnitOfMeasure.objects.create(organization=self.org,code="cm-sales",name="Centimeter",symbol="cm",category="length",ratio_to_base=Decimal("0.01"),rounding=Decimal("0.1"));self.definition=MeasurementDefinition.objects.create(organization=self.org,code="chest-sales",name="Chest",unit=self.unit);self.ms=MeasurementSet.objects.create(organization=self.org,company=self.company,customer=self.customer,version=1,measured_at=timezone.now(),created_by=self.user);MeasurementValue.objects.create(measurement_set=self.ms,definition=self.definition,value=Decimal("92"))
 def test_full_quote_order_confirmation_freezes_measurements(self):
  q=self.client.post("/api/v1/sales/quotations/",{"company":str(self.company.id),"customer":str(self.customer.id),"currency":str(self.currency.pk),"number":"Q-001","lines":[{"description":"Custom garment","quantity":"1","unit_price":"50000","discount_rate":"0"}]},format="json");self.assertEqual(q.status_code,status.HTTP_201_CREATED)
  self.assertEqual(self.client.post(f"/api/v1/sales/quotations/{q.data['id']}/actions/send/").data["status"],"sent");self.assertEqual(self.client.post(f"/api/v1/sales/quotations/{q.data['id']}/actions/accept/").data["status"],"accepted")
  o=self.client.post("/api/v1/sales/orders/",{"company":str(self.company.id),"customer":str(self.customer.id),"quotation":q.data["id"],"number":"O-001","lines":[{"description":"Custom garment","quantity":"1","unit_price":"50000","measurement_set":str(self.ms.id)}]},format="json");self.assertEqual(o.status_code,status.HTTP_201_CREATED)
  confirmed=self.client.post(f"/api/v1/sales/orders/{o.data['id']}/actions/confirm/");self.assertEqual(confirmed.status_code,status.HTTP_200_OK);self.assertEqual(confirmed.data["status"],"confirmed");self.assertEqual(confirmed.data["lines"][0]["measurement_snapshot"]["version"],1)
  MeasurementValue.objects.filter(measurement_set=self.ms).update(value=Decimal("99"));confirmed_again=self.client.post(f"/api/v1/sales/orders/{o.data['id']}/actions/confirm/");self.assertEqual(confirmed_again.status_code,status.HTTP_400_BAD_REQUEST)
 def test_status_cannot_be_patched_through_collection_payload(self):
  q=self.client.post("/api/v1/sales/quotations/",{"company":str(self.company.id),"customer":str(self.customer.id),"currency":str(self.currency.pk),"number":"Q-002","status":"accepted","lines":[]},format="json");self.assertEqual(q.data["status"],"draft")

 def test_rejects_cross_scope_measurement_reference(self):
  other=self.org; other_company=Company.objects.create(organization=other,name="Other Maison",code="other-maison"); other_customer=Customer.objects.create(organization=other,company=other_company,code="OC1",display_name="Other Client")
  other_ms=MeasurementSet.objects.create(organization=other,company=other_company,customer=other_customer,version=1,measured_at=timezone.now(),created_by=self.user)
  response=self.client.post("/api/v1/sales/orders/",{"company":str(self.company.id),"customer":str(self.customer.id),"number":"O-XTENANT","lines":[{"description":"Custom garment","quantity":"1","unit_price":"50000","measurement_set":str(other_ms.id)}]},format="json")
  self.assertEqual(response.status_code,status.HTTP_400_BAD_REQUEST)
