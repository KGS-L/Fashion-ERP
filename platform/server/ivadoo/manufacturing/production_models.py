import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class ManufacturingMaterialConsumption(models.Model):
    class SourceType(models.TextChoices):
        RESERVED = "reserved", "Reserved material"
        SUPPLEMENTAL = "supplemental", "Supplemental material"

    class Disposition(models.TextChoices):
        CONSUMED = "consumed", "Consumed"
        SCRAP = "scrap", "Scrap / loss"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="manufacturing_material_consumptions",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="manufacturing_material_consumptions",
    )
    manufacturing_order = models.ForeignKey(
        "manufacturing.ManufacturingOrder",
        on_delete=models.PROTECT,
        related_name="material_consumptions",
    )
    requirement = models.ForeignKey(
        "manufacturing.ManufacturingMaterialRequirement",
        on_delete=models.PROTECT,
        related_name="consumptions",
    )
    reservation = models.ForeignKey(
        "inventory.StockReservation",
        on_delete=models.PROTECT,
        related_name="manufacturing_consumptions",
        null=True,
        blank=True,
    )
    source_location = models.ForeignKey(
        "inventory.StockLocation",
        on_delete=models.PROTECT,
        related_name="manufacturing_consumptions",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="manufacturing_consumptions",
    )
    product_variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="manufacturing_consumptions",
        null=True,
        blank=True,
    )
    unit = models.ForeignKey(
        "internationalization.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="manufacturing_consumptions",
    )
    lot = models.ForeignKey(
        "inventory.StockLot",
        on_delete=models.PROTECT,
        related_name="manufacturing_consumptions",
        null=True,
        blank=True,
    )
    stock_movement = models.OneToOneField(
        "inventory.StockMovement",
        on_delete=models.PROTECT,
        related_name="manufacturing_consumption",
    )
    source_type = models.CharField(max_length=16, choices=SourceType.choices)
    disposition = models.CharField(
        max_length=16,
        choices=Disposition.choices,
        default=Disposition.CONSUMED,
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    reason = models.CharField(max_length=255, blank=True)
    idempotency_key = models.CharField(max_length=160)
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_manufacturing_material_consumptions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="manufacturing_consumption_quantity_positive",
            ),
            models.UniqueConstraint(
                fields=("organization", "idempotency_key"),
                name="manufacturing_consumption_unique_idempotency_org",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Manufacturing material consumptions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Manufacturing material consumptions are immutable.")


class ManufacturingMaterialRemnant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="manufacturing_material_remnants",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="manufacturing_material_remnants",
    )
    manufacturing_order = models.ForeignKey(
        "manufacturing.ManufacturingOrder",
        on_delete=models.PROTECT,
        related_name="material_remnants",
    )
    requirement = models.ForeignKey(
        "manufacturing.ManufacturingMaterialRequirement",
        on_delete=models.PROTECT,
        related_name="remnants",
    )
    location = models.ForeignKey(
        "inventory.StockLocation",
        on_delete=models.PROTECT,
        related_name="manufacturing_remnants",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="manufacturing_remnants",
    )
    product_variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="manufacturing_remnants",
        null=True,
        blank=True,
    )
    unit = models.ForeignKey(
        "internationalization.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="manufacturing_remnants",
    )
    stock_lot = models.OneToOneField(
        "inventory.StockLot",
        on_delete=models.PROTECT,
        related_name="manufacturing_remnant",
    )
    stock_movement = models.OneToOneField(
        "inventory.StockMovement",
        on_delete=models.PROTECT,
        related_name="manufacturing_remnant",
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    reason = models.CharField(max_length=255, blank=True)
    idempotency_key = models.CharField(max_length=160)
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_manufacturing_material_remnants",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="manufacturing_remnant_quantity_positive",
            ),
            models.UniqueConstraint(
                fields=("organization", "idempotency_key"),
                name="manufacturing_remnant_unique_idempotency_org",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Manufacturing material remnants are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Manufacturing material remnants are immutable.")


class ManufacturingOutputReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="manufacturing_output_receipts",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="manufacturing_output_receipts",
    )
    manufacturing_order = models.OneToOneField(
        "manufacturing.ManufacturingOrder",
        on_delete=models.PROTECT,
        related_name="output_receipt",
    )
    destination_location = models.ForeignKey(
        "inventory.StockLocation",
        on_delete=models.PROTECT,
        related_name="manufacturing_output_receipts",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="manufacturing_output_receipts",
    )
    product_variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="manufacturing_output_receipts",
        null=True,
        blank=True,
    )
    unit = models.ForeignKey(
        "internationalization.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="manufacturing_output_receipts",
    )
    stock_movement = models.OneToOneField(
        "inventory.StockMovement",
        on_delete=models.PROTECT,
        related_name="manufacturing_output_receipt",
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_manufacturing_output_receipts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="manufacturing_output_quantity_positive",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Manufacturing output receipts are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Manufacturing output receipts are immutable.")
