from rest_framework import serializers

from ivadoo.sales.models import Order, OrderLine

from .models import Delivery, DeliveryLine, DeliveryPackage, DeliveryProof
from .services import create_delivery


class DeliveryLineSerializer(serializers.ModelSerializer):
    order_line_id = serializers.PrimaryKeyRelatedField(source="order_line", queryset=OrderLine.objects.all())

    class Meta:
        model = DeliveryLine
        fields = ("id", "order_line_id", "quantity")
        read_only_fields = ("id",)


class DeliveryPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryPackage
        fields = ("id", "code", "description", "is_sealed", "notes", "created_at")
        read_only_fields = ("id", "created_at")


class DeliveryProofSerializer(serializers.ModelSerializer):
    recorded_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = DeliveryProof
        fields = ("id", "proof_type", "recipient_name", "evidence_reference", "notes", "recorded_by_id", "recorded_at")
        read_only_fields = fields


class DeliverySerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    order_id = serializers.PrimaryKeyRelatedField(source="order", queryset=Order.objects.all())
    created_by_id = serializers.UUIDField(read_only=True)
    lines = DeliveryLineSerializer(many=True)
    packages = DeliveryPackageSerializer(many=True, required=False)
    proof = DeliveryProofSerializer(read_only=True)

    class Meta:
        model = Delivery
        fields = (
            "id", "organization_id", "company_id", "order_id", "number", "mode", "status",
            "courier_name", "courier_reference", "destination_notes", "failure_reason",
            "created_by_id", "prepared_at", "assigned_at", "shipped_at", "completed_at", "failed_at",
            "created_at", "updated_at", "lines", "packages", "proof",
        )
        read_only_fields = (
            "id", "organization_id", "company_id", "status", "failure_reason", "created_by_id",
            "prepared_at", "assigned_at", "shipped_at", "completed_at", "failed_at", "created_at", "updated_at", "proof",
        )

    def validate(self, attrs):
        request = self.context["request"]
        order = attrs["order"]
        if order.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"order_id": "Order is outside the local organization."})
        if order.status != Order.Status.CONFIRMED:
            raise serializers.ValidationError({"order_id": "Delivery requires a confirmed order."})
        lines = attrs.get("lines", [])
        if not lines:
            raise serializers.ValidationError({"lines": "At least one delivery line is required."})
        for line in lines:
            if line["order_line"].order_id != order.id:
                raise serializers.ValidationError({"lines": "Every delivery line must belong to the selected order."})
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop("lines")
        packages = validated_data.pop("packages", [])
        return create_delivery(
            lines=lines,
            packages=packages,
            actor=self.context["request"].user,
            request=self.context["request"],
            **validated_data,
        )


class DeliveryProofInputSerializer(serializers.Serializer):
    proof_type = serializers.ChoiceField(choices=DeliveryProof.ProofType.choices)
    recipient_name = serializers.CharField(max_length=160)
    evidence_reference = serializers.CharField(max_length=500, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class DeliveryActionSerializer(serializers.Serializer):
    proof = DeliveryProofInputSerializer(required=False)
    failure_reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
