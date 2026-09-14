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
        value = value.upper()
        if self.instance is not None and value != self.instance.code:
            raise serializers.ValidationError(
                "Currency code cannot be changed."
            )
        return value


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
        base_currency = attrs.get(
            "base_currency",
            getattr(self.instance, "base_currency", None),
        )
        quote_currency = attrs.get(
            "quote_currency",
            getattr(self.instance, "quote_currency", None),
        )
        if (
            base_currency is not None
            and quote_currency is not None
            and base_currency.pk == quote_currency.pk
        ):
            raise serializers.ValidationError(
                {
                    "quote_currency_code": (
                        "Base and quote currencies must differ."
                    )
                }
            )
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
