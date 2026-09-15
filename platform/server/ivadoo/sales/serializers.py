from rest_framework import serializers
from ivadoo.catalog.models import FashionModel,FashionModelVariant
from ivadoo.customers.models import Customer
from ivadoo.internationalization.models import Currency
from ivadoo.measurements.models import MeasurementSet
from ivadoo.organizations.models import Company
from .models import Order,OrderLine,Quotation,QuotationLine

def _org(request):
    return request.user.organization_id if request else None

class QuotationLineSerializer(serializers.ModelSerializer):
    class Meta:
        model=QuotationLine
        fields=("id","fashion_model","model_variant","description","quantity","unit_price","discount_rate")
        read_only_fields=("id",)
    def validate(self,attrs):
        request=self.context.get("request"); org_id=_org(request)
        model=attrs.get("fashion_model"); variant=attrs.get("model_variant")
        if model and model.organization_id!=org_id: raise serializers.ValidationError({"fashion_model":"Fashion model is outside the organization."})
        if variant and variant.fashion_model.organization_id!=org_id: raise serializers.ValidationError({"model_variant":"Model variant is outside the organization."})
        if model and variant and variant.fashion_model_id!=model.id: raise serializers.ValidationError({"model_variant":"Variant does not belong to the selected fashion model."})
        return attrs

class QuotationSerializer(serializers.ModelSerializer):
    lines=QuotationLineSerializer(many=True); status=serializers.CharField(read_only=True)
    class Meta:
        model=Quotation
        fields=("id","company","customer","currency","number","status","valid_until","notes","lines","created_at","updated_at")
        read_only_fields=("id","created_at","updated_at")
    def validate(self,attrs):
        request=self.context.get("request"); org_id=_org(request); company=attrs["company"]; customer=attrs["customer"]
        if company.organization_id!=org_id or customer.organization_id!=org_id: raise serializers.ValidationError("Company and customer must belong to the local organization.")
        if customer.company_id!=company.id: raise serializers.ValidationError({"customer":"Customer must belong to the selected company."})
        return attrs
    def create(self,d):
        lines=d.pop("lines"); q=Quotation.objects.create(**d); QuotationLine.objects.bulk_create([QuotationLine(quotation=q,**x) for x in lines]); return q

class OrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model=OrderLine
        fields=("id","fashion_model","model_variant","description","quantity","unit_price","measurement_set","measurement_snapshot","measurement_source_version")
        read_only_fields=("id","measurement_snapshot","measurement_source_version")
    def validate(self,attrs):
        request=self.context.get("request"); org_id=_org(request)
        model=attrs.get("fashion_model"); variant=attrs.get("model_variant"); ms=attrs.get("measurement_set")
        if model and model.organization_id!=org_id: raise serializers.ValidationError({"fashion_model":"Fashion model is outside the organization."})
        if variant and variant.fashion_model.organization_id!=org_id: raise serializers.ValidationError({"model_variant":"Model variant is outside the organization."})
        if model and variant and variant.fashion_model_id!=model.id: raise serializers.ValidationError({"model_variant":"Variant does not belong to the selected fashion model."})
        if ms and ms.organization_id!=org_id: raise serializers.ValidationError({"measurement_set":"Measurement set is outside the organization."})
        return attrs

class OrderSerializer(serializers.ModelSerializer):
    lines=OrderLineSerializer(many=True); status=serializers.CharField(read_only=True); confirmed_at=serializers.DateTimeField(read_only=True); cancelled_at=serializers.DateTimeField(read_only=True)
    class Meta:
        model=Order
        fields=("id","company","customer","quotation","number","status","delivery_date","event_date","lines","confirmed_at","cancelled_at","created_at","updated_at")
        read_only_fields=("id","created_at","updated_at")
    def validate(self,attrs):
        request=self.context.get("request"); org_id=_org(request); company=attrs["company"]; customer=attrs["customer"]; quotation=attrs.get("quotation")
        if company.organization_id!=org_id or customer.organization_id!=org_id: raise serializers.ValidationError("Company and customer must belong to the local organization.")
        if customer.company_id!=company.id: raise serializers.ValidationError({"customer":"Customer must belong to the selected company."})
        if quotation and (quotation.organization_id!=org_id or quotation.company_id!=company.id or quotation.customer_id!=customer.id): raise serializers.ValidationError({"quotation":"Quotation must belong to the same organization, company and customer."})
        for line in attrs["lines"]:
            ms=line.get("measurement_set")
            if ms and (ms.customer_id!=customer.id or ms.company_id!=company.id): raise serializers.ValidationError({"lines":"Measurement set must belong to the order customer and company."})
        return attrs
    def create(self,d):
        lines=d.pop("lines"); o=Order.objects.create(**d); OrderLine.objects.bulk_create([OrderLine(order=o,**x) for x in lines]); return o
