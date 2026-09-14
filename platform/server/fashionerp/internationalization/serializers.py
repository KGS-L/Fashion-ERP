from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Currency, ExchangeRate, UnitOfMeasure


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = (
            "code",
            "name",
            "symbol",
            "decimal_places",
            "rounding",
            "is_active",
        )

    def validate_code(self, value):
        return value.upper()


class ExchangeRateSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    base_currency_code = serializers.PrimaryKeyRelatedField(
        source="base_currency",
        queryset=Currency.objects.filter(is_active=True),
    )
    quote_currency_code = serializers.PrimaryKeyRelatedField(
        source="quote_currency",
        queryset=Currency.objects.filter(is_active=True),
    )

    class Meta:
        model = ExchangeRate
        fields = (
            "id",
            "organization_id",
            "base_currency_code",
            "quote_currency_code",
            "valid_on",
            "rate",
            "created_at",
        )
        read_only_fields = ("id", "organization_id", "created_at")

    def validate(self, attrs):
        instance = ExchangeRate(
            organization=self.context["request"].user.organization,
            **attrs,
        )
        try:
            instance.full_clean(exclude=("id",))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict or exc.messages
            ) from exc
        return attrs

    def create(self, validated_data):
        return ExchangeRate.objects.create(
            organization=self.context["request"].user.organization,
            **validated_data,
        )


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = UnitOfMeasure
        fields = (
            "id",
            "organization_id",
            "code",
            "name",
            "symbol",
            "category",
            "ratio_to_base",
            "rounding",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "created_at",
            "updated_at",
        )

    def create(self, validated_data):
        return UnitOfMeasure.objects.create(
            organization=self.context["request"].user.organization,
            **validated_data,
        )
