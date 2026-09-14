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

        valid_on = attrs.get(
            "valid_on",
            getattr(self.instance, "valid_on", None),
        )
        if base_currency and quote_currency and valid_on:
            duplicate = ExchangeRate.objects.filter(
                organization=self.context["request"].user.organization,
                base_currency=base_currency,
                quote_currency=quote_currency,
                valid_on=valid_on,
            )
            if self.instance is not None:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError(
                    "An exchange rate already exists for this currency pair and date."
                )
        return attrs

    def create(self, validated_data):
        return ExchangeRate.objects.create(
            organization=self.context["request"].user.organization,
            **validated_data,
        )


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)

    def validate_code(self, value):
        organization = self.context["request"].user.organization
        duplicate = UnitOfMeasure.objects.filter(
            organization=organization,
            code=value,
        )
        if self.instance is not None:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                "Unit code already exists in this organization."
            )
        return value

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


class LanguageOptionSerializer(serializers.Serializer):
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    direction = serializers.ChoiceField(
        choices=("ltr", "rtl"),
        read_only=True,
    )


class TranslationCatalogResponseSerializer(serializers.Serializer):
    language = serializers.CharField(read_only=True)
    direction = serializers.ChoiceField(
        choices=("ltr", "rtl"),
        read_only=True,
    )
    catalog = serializers.JSONField(read_only=True)
    formats = serializers.JSONField(read_only=True)


class InternationalizationContextResponseSerializer(serializers.Serializer):
    language = serializers.CharField(read_only=True)
    direction = serializers.ChoiceField(
        choices=("ltr", "rtl"),
        read_only=True,
    )
    formats = serializers.JSONField(read_only=True)
    functional_currency = CurrencySerializer(
        read_only=True,
        allow_null=True,
    )
    timezone = serializers.CharField(read_only=True)
    company_id = serializers.UUIDField(read_only=True, allow_null=True)
    establishment_id = serializers.UUIDField(
        read_only=True,
        allow_null=True,
    )
