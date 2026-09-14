import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


currency_code_validator = RegexValidator(
    regex=r"^[A-Z]{3}$",
    message="Currency code must be a three-letter uppercase code.",
)


class Currency(models.Model):
    code = models.CharField(
        primary_key=True,
        max_length=3,
        validators=[currency_code_validator],
    )
    name = models.CharField(max_length=120)
    symbol = models.CharField(max_length=16, blank=True)
    decimal_places = models.PositiveSmallIntegerField()
    rounding = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        validators=[MinValueValidator(Decimal("0.00000001"))],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.code


class ExchangeRate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="exchange_rates",
    )
    base_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="base_exchange_rates",
    )
    quote_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="quote_exchange_rates",
    )
    valid_on = models.DateField(db_index=True)
    rate = models.DecimalField(
        max_digits=28,
        decimal_places=12,
        validators=[MinValueValidator(Decimal("0.000000000001"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-valid_on", "base_currency_id", "quote_currency_id")
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "organization",
                    "base_currency",
                    "quote_currency",
                    "valid_on",
                ),
                name="i18n_unique_dated_exchange_rate",
            ),
            models.CheckConstraint(
                condition=~models.Q(
                    base_currency=models.F("quote_currency")
                ),
                name="i18n_exchange_rate_distinct_currencies",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.base_currency_id == self.quote_currency_id:
            raise ValidationError(
                {"quote_currency": "Base and quote currencies must differ."}
            )

    def __str__(self) -> str:
        return (
            f"{self.base_currency_id}/{self.quote_currency_id} "
            f"{self.valid_on}"
        )


class UnitOfMeasure(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="units_of_measure",
    )
    code = models.SlugField(max_length=64)
    name = models.CharField(max_length=120)
    symbol = models.CharField(max_length=32, blank=True)
    category = models.CharField(max_length=64)
    ratio_to_base = models.DecimalField(
        max_digits=28,
        decimal_places=12,
        validators=[MinValueValidator(Decimal("0.000000000001"))],
    )
    rounding = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        validators=[MinValueValidator(Decimal("0.00000001"))],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("category", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="i18n_unique_unit_code_per_org",
            ),
        ]

    def __str__(self) -> str:
        return self.name
