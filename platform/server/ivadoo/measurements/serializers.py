from django.db import transaction
from django.db.models import Max
from rest_framework import serializers

from ivadoo.customers.models import Customer
from ivadoo.organizations.models import Company, Establishment

from .models import (
    MeasurementDefinition,
    MeasurementProfile,
    MeasurementSet,
    MeasurementValue,
)


class MeasurementValueSerializer(serializers.ModelSerializer):
    definition_id = serializers.PrimaryKeyRelatedField(
        source="definition", queryset=MeasurementDefinition.objects.all()
    )

    class Meta:
        model = MeasurementValue
        fields = ("id", "definition_id", "value", "tolerance", "note")
        read_only_fields = ("id",)


class MeasurementSetSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )
    establishment_id = serializers.PrimaryKeyRelatedField(
        source="establishment",
        queryset=Establishment.objects.all(),
        required=False,
        allow_null=True,
    )
    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer", queryset=Customer.objects.all()
    )
    profile_id = serializers.PrimaryKeyRelatedField(
        source="profile",
        queryset=MeasurementProfile.objects.all(),
        required=False,
        allow_null=True,
    )
    values = MeasurementValueSerializer(many=True)
    version = serializers.IntegerField(read_only=True)
    created_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = MeasurementSet
        fields = (
            "id",
            "company_id",
            "establishment_id",
            "customer_id",
            "profile_id",
            "version",
            "measured_at",
            "notes",
            "alteration_notes",
            "media_references",
            "values",
            "created_by_id",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        customer = attrs["customer"]
        company = attrs["company"]
        establishment = attrs.get("establishment")
        profile = attrs.get("profile")
        if company.organization_id != customer.organization_id:
            raise serializers.ValidationError(
                "Company and customer must share an organization."
            )
        if customer.company_id != company.id:
            raise serializers.ValidationError(
                "Company must match the customer company."
            )
        if establishment and establishment.company_id != company.id:
            raise serializers.ValidationError(
                "Establishment must belong to the company."
            )
        if profile and profile.organization_id != customer.organization_id:
            raise serializers.ValidationError(
                "Profile must belong to the organization."
            )
        for item in attrs["values"]:
            if item["definition"].organization_id != customer.organization_id:
                raise serializers.ValidationError(
                    "Measurement definition is outside the organization."
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        values = validated_data.pop("values")
        customer = validated_data["customer"]

        # A measurement version is a per-customer sequence. Lock the stable
        # customer row before reading the current maximum so two concurrent
        # recordings cannot allocate the same next version.
        locked_customer = Customer.objects.select_for_update().get(pk=customer.pk)
        next_version = (
            MeasurementSet.objects.filter(customer=locked_customer).aggregate(
                max_version=Max("version")
            )["max_version"]
            or 0
        ) + 1

        measurement_set = MeasurementSet.objects.create(
            customer=locked_customer,
            version=next_version,
            **{
                key: value
                for key, value in validated_data.items()
                if key != "customer"
            },
        )
        MeasurementValue.objects.bulk_create(
            [
                MeasurementValue(measurement_set=measurement_set, **item)
                for item in values
            ]
        )
        return measurement_set
