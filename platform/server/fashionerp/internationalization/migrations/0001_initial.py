import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0002_company_establishment"),
    ]

    operations = [
        migrations.CreateModel(
            name="Currency",
            fields=[
                (
                    "code",
                    models.CharField(
                        max_length=3,
                        primary_key=True,
                        serialize=False,
                        validators=[
                            django.core.validators.RegexValidator(
                                message=(
                                    "Currency code must be a three-letter "
                                    "uppercase code."
                                ),
                                regex="^[A-Z]{3}$",
                            )
                        ],
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("symbol", models.CharField(blank=True, max_length=16)),
                ("decimal_places", models.PositiveSmallIntegerField()),
                (
                    "rounding",
                    models.DecimalField(
                        decimal_places=8,
                        max_digits=18,
                        validators=[
                            django.core.validators.MinValueValidator(
                                Decimal("1E-8")
                            )
                        ],
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ("code",)},
        ),
        migrations.CreateModel(
            name="ExchangeRate",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("valid_on", models.DateField(db_index=True)),
                (
                    "rate",
                    models.DecimalField(
                        decimal_places=12,
                        max_digits=28,
                        validators=[
                            django.core.validators.MinValueValidator(
                                Decimal("1E-12")
                            )
                        ],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "base_currency",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="base_exchange_rates",
                        to="internationalization.currency",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exchange_rates",
                        to="organizations.organization",
                    ),
                ),
                (
                    "quote_currency",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="quote_exchange_rates",
                        to="internationalization.currency",
                    ),
                ),
            ],
            options={
                "ordering": (
                    "-valid_on",
                    "base_currency_id",
                    "quote_currency_id",
                )
            },
        ),
        migrations.CreateModel(
            name="UnitOfMeasure",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("code", models.SlugField(max_length=64)),
                ("name", models.CharField(max_length=120)),
                ("symbol", models.CharField(blank=True, max_length=32)),
                ("category", models.CharField(max_length=64)),
                (
                    "ratio_to_base",
                    models.DecimalField(
                        decimal_places=12,
                        max_digits=28,
                        validators=[
                            django.core.validators.MinValueValidator(
                                Decimal("1E-12")
                            )
                        ],
                    ),
                ),
                (
                    "rounding",
                    models.DecimalField(
                        decimal_places=8,
                        max_digits=18,
                        validators=[
                            django.core.validators.MinValueValidator(
                                Decimal("1E-8")
                            )
                        ],
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="units_of_measure",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={"ordering": ("category", "name")},
        ),
        migrations.AddConstraint(
            model_name="exchangerate",
            constraint=models.UniqueConstraint(
                fields=(
                    "organization",
                    "base_currency",
                    "quote_currency",
                    "valid_on",
                ),
                name="i18n_unique_dated_exchange_rate",
            ),
        ),
        migrations.AddConstraint(
            model_name="exchangerate",
            constraint=models.CheckConstraint(
                condition=~models.Q(
                    ("base_currency", models.F("quote_currency"))
                ),
                name="i18n_exchange_rate_distinct_currencies",
            ),
        ),
        migrations.AddConstraint(
            model_name="unitofmeasure",
            constraint=models.UniqueConstraint(
                fields=("organization", "code"),
                name="i18n_unique_unit_code_per_org",
            ),
        ),
    ]
