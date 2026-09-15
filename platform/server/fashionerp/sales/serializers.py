from rest_framework import serializers
from fashionerp.catalog.models import FashionModel,FashionModelVariant
from fashionerp.customers.models import Customer
from fashionerp.internationalization.models import Currency
from fashionerp.measurements.models import MeasurementSet
from fashionerp.organizations.models import Company
from .models import Order,OrderLine,Quotation,QuotationLine

class QuotationLineSerializer(serializers.ModelSerializer):
    class Meta: model=QuotationLine; fields=("id","fashion_model","model_variant","description","quantity","unit_price","discount_rate"); read_only_fields=("id",)
class QuotationSerializer(serializers.ModelSerializer):
    lines=QuotationLineSerializer(many=True); status=serializers.CharField(read_only=True)
    class Meta: model=Quotation; fields=("id","company","customer","currency","number","status","valid_until","notes","lines","created_at","updated_at"); read_only_fields=("id","created_at","updated_at")
    def create(self,d):
        lines=d.pop("lines"); q=Quotation.objects.create(**d); QuotationLine.objects.bulk_create([QuotationLine(quotation=q,**x) for x in lines]); return q

class OrderLineSerializer(serializers.ModelSerializer):
    class Meta: model=OrderLine; fields=("id","fashion_model","model_variant","description","quantity","unit_price","measurement_set","measurement_snapshot","measurement_source_version"); read_only_fields=("id","measurement_snapshot","measurement_source_version")
class OrderSerializer(serializers.ModelSerializer):
    lines=OrderLineSerializer(many=True); status=serializers.CharField(read_only=True); confirmed_at=serializers.DateTimeField(read_only=True); cancelled_at=serializers.DateTimeField(read_only=True)
    class Meta: model=Order; fields=("id","company","customer","quotation","number","status","delivery_date","event_date","lines","confirmed_at","cancelled_at","created_at","updated_at"); read_only_fields=("id","created_at","updated_at")
    def create(self,d):
        lines=d.pop("lines"); o=Order.objects.create(**d); OrderLine.objects.bulk_create([OrderLine(order=o,**x) for x in lines]); return o
