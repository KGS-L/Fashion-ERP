import uuid
from django.db import models

class Quotation(models.Model):
    class Status(models.TextChoices):
        DRAFT="draft","Draft"; SENT="sent","Sent"; ACCEPTED="accepted","Accepted"; REJECTED="rejected","Rejected"; EXPIRED="expired","Expired"
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    organization=models.ForeignKey("organizations.Organization",on_delete=models.PROTECT,related_name="quotations")
    company=models.ForeignKey("organizations.Company",on_delete=models.PROTECT,related_name="quotations")
    customer=models.ForeignKey("customers.Customer",on_delete=models.PROTECT,related_name="quotations")
    currency=models.ForeignKey("internationalization.Currency",on_delete=models.PROTECT,related_name="quotations")
    number=models.CharField(max_length=64); status=models.CharField(max_length=16,choices=Status.choices,default=Status.DRAFT)
    valid_until=models.DateField(null=True,blank=True); notes=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta: constraints=[models.UniqueConstraint(fields=("organization","number"),name="quotation_unique_number_org")]

class QuotationLine(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); quotation=models.ForeignKey(Quotation,on_delete=models.CASCADE,related_name="lines")
    fashion_model=models.ForeignKey("catalog.FashionModel",on_delete=models.PROTECT,null=True,blank=True,related_name="quotation_lines")
    model_variant=models.ForeignKey("catalog.FashionModelVariant",on_delete=models.PROTECT,null=True,blank=True,related_name="quotation_lines")
    description=models.CharField(max_length=255); quantity=models.DecimalField(max_digits=14,decimal_places=4,default=1); unit_price=models.DecimalField(max_digits=14,decimal_places=4); discount_rate=models.DecimalField(max_digits=7,decimal_places=4,default=0)

class Order(models.Model):
    class Status(models.TextChoices): DRAFT="draft","Draft"; CONFIRMED="confirmed","Confirmed"; CANCELLED="cancelled","Cancelled"
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); organization=models.ForeignKey("organizations.Organization",on_delete=models.PROTECT,related_name="fashion_orders")
    company=models.ForeignKey("organizations.Company",on_delete=models.PROTECT,related_name="fashion_orders"); customer=models.ForeignKey("customers.Customer",on_delete=models.PROTECT,related_name="fashion_orders")
    quotation=models.ForeignKey(Quotation,on_delete=models.PROTECT,null=True,blank=True,related_name="orders"); number=models.CharField(max_length=64); status=models.CharField(max_length=16,choices=Status.choices,default=Status.DRAFT)
    delivery_date=models.DateField(null=True,blank=True); event_date=models.DateField(null=True,blank=True); confirmed_at=models.DateTimeField(null=True,blank=True); cancelled_at=models.DateTimeField(null=True,blank=True); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta: constraints=[models.UniqueConstraint(fields=("organization","number"),name="fashion_order_unique_number_org")]

class OrderLine(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); order=models.ForeignKey(Order,on_delete=models.CASCADE,related_name="lines")
    fashion_model=models.ForeignKey("catalog.FashionModel",on_delete=models.PROTECT,null=True,blank=True,related_name="order_lines"); model_variant=models.ForeignKey("catalog.FashionModelVariant",on_delete=models.PROTECT,null=True,blank=True,related_name="order_lines")
    description=models.CharField(max_length=255); quantity=models.DecimalField(max_digits=14,decimal_places=4,default=1); unit_price=models.DecimalField(max_digits=14,decimal_places=4)
    measurement_set=models.ForeignKey("measurements.MeasurementSet",on_delete=models.PROTECT,null=True,blank=True,related_name="order_lines")
    measurement_snapshot=models.JSONField(default=dict,blank=True); measurement_source_version=models.PositiveIntegerField(null=True,blank=True)


from .fitting_models import AlterationRequest, CustomerValidation, FittingSession  # noqa: E402,F401
