from django.db import transaction
from rest_framework import serializers

from ivadoo.manufacturing.models import ManufacturingOperation, ManufacturingOrder
from ivadoo.manufacturing.production_models import ManufacturingOutputReceipt
from ivadoo.organizations.models import Company
from ivadoo.purchases.models import PurchaseReceiptLine

from .models import QualityCriterion, QualityDefect, QualityInspection, QualityRework


class QualityCriterionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QualityCriterion
        fields = ("id", "code", "label", "expected_value", "result", "notes", "position")
        read_only_fields = ("id",)


class QualityDefectSerializer(serializers.ModelSerializer):
    photo_references = serializers.ListField(child=serializers.CharField(max_length=500), required=False)

    class Meta:
        model = QualityDefect
        fields = ("id", "code", "severity", "description", "quantity", "photo_references", "created_at")
        read_only_fields = ("id", "created_at")


class QualityInspectionSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(source="company", queryset=Company.objects.all())
    purchase_receipt_line_id = serializers.PrimaryKeyRelatedField(source="purchase_receipt_line", queryset=PurchaseReceiptLine.objects.all(), allow_null=True, required=False)
    manufacturing_order_id = serializers.PrimaryKeyRelatedField(source="manufacturing_order", queryset=ManufacturingOrder.objects.all(), allow_null=True, required=False)
    manufacturing_operation_id = serializers.PrimaryKeyRelatedField(source="manufacturing_operation", queryset=ManufacturingOperation.objects.all(), allow_null=True, required=False)
    output_receipt_id = serializers.PrimaryKeyRelatedField(source="output_receipt", queryset=ManufacturingOutputReceipt.objects.all(), allow_null=True, required=False)
    parent_inspection_id = serializers.PrimaryKeyRelatedField(source="parent_inspection", queryset=QualityInspection.objects.all(), allow_null=True, required=False)
    created_by_id = serializers.UUIDField(read_only=True)
    completed_by_id = serializers.UUIDField(read_only=True, allow_null=True)
    criteria = QualityCriterionSerializer(many=True, required=False)
    defects = QualityDefectSerializer(many=True, required=False)

    class Meta:
        model = QualityInspection
        fields = (
            "id", "organization_id", "company_id", "inspection_type", "status", "decision", "blocking",
            "purchase_receipt_line_id", "manufacturing_order_id", "manufacturing_operation_id", "output_receipt_id",
            "parent_inspection_id", "notes", "completion_reason", "created_by_id", "completed_by_id", "completed_at",
            "created_at", "updated_at", "criteria", "defects",
        )
        read_only_fields = ("id", "organization_id", "status", "decision", "completion_reason", "created_by_id", "completed_by_id", "completed_at", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context["request"]
        company = attrs["company"]
        if company.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"company_id": "Company is outside the local organization."})
        contexts = [
            attrs.get("purchase_receipt_line"), attrs.get("manufacturing_order"),
            attrs.get("manufacturing_operation"), attrs.get("output_receipt"),
        ]
        if sum(value is not None for value in contexts) != 1:
            raise serializers.ValidationError("Exactly one inspection context is required.")
        parent = attrs.get("parent_inspection")
        if parent and (parent.organization_id != request.user.organization_id or parent.company_id != company.id):
            raise serializers.ValidationError({"parent_inspection_id": "Parent inspection is outside the local scope."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        criteria = validated_data.pop("criteria", [])
        defects = validated_data.pop("defects", [])
        inspection = QualityInspection(**validated_data)
        inspection.full_clean()
        inspection.save()
        for item in criteria:
            QualityCriterion.objects.create(inspection=inspection, **item)
        for item in defects:
            QualityDefect.objects.create(inspection=inspection, **item)
        return inspection


class QualityInspectionCompleteSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=(QualityInspection.Decision.ACCEPT, QualityInspection.Decision.REJECT, QualityInspection.Decision.REWORK))
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
    rework_instructions = serializers.CharField(required=False, allow_blank=True)


class QualityReworkSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    inspection_id = serializers.UUIDField(read_only=True)
    manufacturing_operation_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by_id = serializers.UUIDField(read_only=True)
    completed_by_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = QualityRework
        fields = (
            "id", "organization_id", "company_id", "inspection_id", "manufacturing_operation_id",
            "status", "instructions", "result_notes", "created_by_id", "completed_by_id", "completed_at", "created_at", "updated_at",
        )
        read_only_fields = fields


class QualityReworkCompleteSerializer(serializers.Serializer):
    result_notes = serializers.CharField(required=False, allow_blank=True)


class QualitySummarySerializer(serializers.Serializer):
    total = serializers.IntegerField()
    accepted = serializers.IntegerField()
    rejected = serializers.IntegerField()
    rework = serializers.IntegerField()
    with_defects = serializers.IntegerField()
    defect_count = serializers.IntegerField()
    defect_rate_percent = serializers.FloatField()
