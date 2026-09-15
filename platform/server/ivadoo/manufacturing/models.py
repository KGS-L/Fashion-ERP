import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class BillOfMaterials(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="manufacturing_boms",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="manufacturing_boms",
    )
    fashion_model = models.ForeignKey(
        "catalog.FashionModel",
        on_delete=models.PROTECT,
        related_name="operational_boms",
    )
    model_variant = models.ForeignKey(
        "catalog.FashionModelVariant",
        on_delete=models.PROTECT,
        related_name="operational_boms",
        null=True,
        blank=True,
    )
    output_product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="manufacturing_output_boms",
        null=True,
        blank=True,
    )
    output_product_variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="manufacturing_output_boms",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=80)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    batch_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_manufacturing_boms",
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code", "-version")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code", "version"),
                name="manufacturing_bom_unique_version_org",
            ),
            models.CheckConstraint(
                condition=models.Q(batch_quantity__gt=0),
                name="manufacturing_bom_batch_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the BOM organization."})
        if self.fashion_model_id:
            if self.fashion_model.organization_id != self.organization_id:
                raise ValidationError({"fashion_model": "Fashion model is outside the BOM organization."})
            if self.fashion_model.company_id and self.fashion_model.company_id != self.company_id:
                raise ValidationError({"fashion_model": "Company-specific fashion model must match BOM company."})
        if self.model_variant_id and self.model_variant.fashion_model_id != self.fashion_model_id:
            raise ValidationError({"model_variant": "Model variant must belong to the selected fashion model."})
        if self.output_product_id:
            if self.output_product.organization_id != self.organization_id:
                raise ValidationError({"output_product": "Output product is outside the BOM organization."})
            if self.output_product.company_id and self.output_product.company_id != self.company_id:
                raise ValidationError({"output_product": "Company-specific output product must match BOM company."})
            if self.output_product.product_type != self.output_product.ProductType.FINISHED_GOOD:
                raise ValidationError({"output_product": "BOM output product must be a finished good."})
        if self.output_product_variant_id:
            if not self.output_product_id or self.output_product_variant.product_id != self.output_product_id:
                raise ValidationError({"output_product_variant": "Output variant must belong to the output product."})

    def __str__(self):
        return f"{self.code} v{self.version}"


class BillOfMaterialsLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bom = models.ForeignKey(
        BillOfMaterials,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="manufacturing_bom_lines",
    )
    product_variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="manufacturing_bom_lines",
        null=True,
        blank=True,
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    unit = models.ForeignKey(
        "internationalization.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="manufacturing_bom_lines",
    )
    waste_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    notes = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="manufacturing_bom_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(waste_rate__gte=0),
                name="manufacturing_bom_line_waste_nonnegative",
            ),
        ]

    def clean(self):
        super().clean()
        organization_id = self.bom.organization_id if self.bom_id else None
        if self.product_id and self.product.organization_id != organization_id:
            raise ValidationError({"product": "Material product is outside the BOM organization."})
        if self.product_id and self.product.company_id and self.product.company_id != self.bom.company_id:
            raise ValidationError({"product": "Company-specific material must match BOM company."})
        if self.product_variant_id and self.product_variant.product_id != self.product_id:
            raise ValidationError({"product_variant": "Material variant must belong to the selected product."})
        if self.unit_id and self.unit.organization_id != organization_id:
            raise ValidationError({"unit": "Unit is outside the BOM organization."})
        if self.product_id and self.unit_id and self.product.unit.category != self.unit.category:
            raise ValidationError({"unit": "Unit category must match the material product unit category."})


class ManufacturingOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="manufacturing_orders",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="manufacturing_orders",
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="manufacturing_orders",
    )
    order = models.ForeignKey(
        "sales.Order",
        on_delete=models.PROTECT,
        related_name="manufacturing_orders",
        null=True,
        blank=True,
    )
    order_line = models.ForeignKey(
        "sales.OrderLine",
        on_delete=models.PROTECT,
        related_name="manufacturing_orders",
        null=True,
        blank=True,
    )
    bom = models.ForeignKey(
        BillOfMaterials,
        on_delete=models.PROTECT,
        related_name="manufacturing_orders",
    )
    number = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    planned_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    produced_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    planned_start = models.DateTimeField(null=True, blank=True)
    planned_end = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    transition_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_manufacturing_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "number"),
                name="manufacturing_order_unique_number_org",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_quantity__gt=0),
                name="manufacturing_order_planned_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(produced_quantity__gte=0),
                name="manufacturing_order_produced_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(produced_quantity__lte=models.F("planned_quantity")),
                name="manufacturing_order_produced_lte_planned",
            ),
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the manufacturing organization."})
        if self.warehouse_id and (
            self.warehouse.organization_id != self.organization_id
            or self.warehouse.company_id != self.company_id
        ):
            raise ValidationError({"warehouse": "Warehouse must belong to the manufacturing company."})
        if self.bom_id and (
            self.bom.organization_id != self.organization_id
            or self.bom.company_id != self.company_id
        ):
            raise ValidationError({"bom": "BOM must belong to the manufacturing company."})
        if self.order_id and (
            self.order.organization_id != self.organization_id
            or self.order.company_id != self.company_id
        ):
            raise ValidationError({"order": "Sales order must belong to the manufacturing company."})
        if self.order_line_id:
            if not self.order_id or self.order_line.order_id != self.order_id:
                raise ValidationError({"order_line": "Order line must belong to the selected sales order."})
            if self.order_line.fashion_model_id and self.order_line.fashion_model_id != self.bom.fashion_model_id:
                raise ValidationError({"bom": "BOM fashion model must match the order line."})
            if self.order_line.model_variant_id and self.bom.model_variant_id and self.order_line.model_variant_id != self.bom.model_variant_id:
                raise ValidationError({"bom": "BOM model variant must match the order line variant."})
        if self.planned_end and self.planned_start and self.planned_end < self.planned_start:
            raise ValidationError({"planned_end": "Planned end cannot precede planned start."})

    def __str__(self):
        return self.number


class ManufacturingMaterialRequirement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    manufacturing_order = models.ForeignKey(
        ManufacturingOrder,
        on_delete=models.CASCADE,
        related_name="material_requirements",
    )
    source_bom_line = models.ForeignKey(
        BillOfMaterialsLine,
        on_delete=models.PROTECT,
        related_name="manufacturing_requirement_snapshots",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="manufacturing_requirements",
    )
    product_variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="manufacturing_requirements",
        null=True,
        blank=True,
    )
    unit = models.ForeignKey(
        "internationalization.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="manufacturing_requirements",
    )
    quantity_per_unit = models.DecimalField(max_digits=18, decimal_places=4)
    waste_rate = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0"))
    planned_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("source_bom_line__position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("manufacturing_order", "source_bom_line"),
                name="manufacturing_requirement_unique_bom_line",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_per_unit__gt=0),
                name="manufacturing_requirement_per_unit_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_quantity__gt=0),
                name="manufacturing_requirement_planned_positive",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Manufacturing material requirement snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Manufacturing material requirement snapshots are immutable.")
