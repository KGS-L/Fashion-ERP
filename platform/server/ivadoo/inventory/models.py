import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="warehouses")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="warehouses")
    establishment = models.ForeignKey("organizations.Establishment", on_delete=models.PROTECT, related_name="warehouses", null=True, blank=True)
    code = models.SlugField(max_length=64)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("organization", "code"), name="inventory_warehouse_unique_code_org"),
        ]
        ordering = ("name",)

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company must belong to the warehouse organization."})
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError({"establishment": "Establishment must belong to the warehouse company."})


class StockLocation(models.Model):
    class Kind(models.TextChoices):
        INTERNAL = "internal", "Internal"
        RECEIVING = "receiving", "Receiving"
        SHIPPING = "shipping", "Shipping"
        PRODUCTION = "production", "Production"
        DAMAGED = "damaged", "Damaged"
        SUBCONTRACTOR = "subcontractor", "Subcontractor"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="locations")
    parent = models.ForeignKey("self", on_delete=models.PROTECT, related_name="children", null=True, blank=True)
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.INTERNAL)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("warehouse", "code"), name="inventory_location_unique_code_warehouse"),
        ]
        ordering = ("warehouse__name", "code")

    @property
    def organization_id(self):
        return self.warehouse.organization_id

    @property
    def company_id(self):
        return self.warehouse.company_id

    @property
    def establishment_id(self):
        return self.warehouse.establishment_id

    def clean(self):
        super().clean()
        if self.parent_id and self.parent.warehouse_id != self.warehouse_id:
            raise ValidationError({"parent": "Parent location must belong to the same warehouse."})


class StockPosition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="stock_positions")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="positions")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="positions")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="stock_positions")
    product_variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="stock_positions", null=True, blank=True)
    unit = models.ForeignKey("internationalization.UnitOfMeasure", on_delete=models.PROTECT, related_name="stock_positions")
    quantity_available = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    quantity_reserved = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    quantity_in_production = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    quantity_damaged = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    quantity_subcontractor = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "location", "product", "product_variant", "unit"),
                name="inventory_position_unique_scope",
                nulls_distinct=False,
            ),
            models.CheckConstraint(condition=models.Q(quantity_available__gte=0), name="inventory_position_available_nonnegative"),
            models.CheckConstraint(condition=models.Q(quantity_reserved__gte=0), name="inventory_position_reserved_nonnegative"),
            models.CheckConstraint(condition=models.Q(quantity_in_production__gte=0), name="inventory_position_production_nonnegative"),
            models.CheckConstraint(condition=models.Q(quantity_damaged__gte=0), name="inventory_position_damaged_nonnegative"),
            models.CheckConstraint(condition=models.Q(quantity_subcontractor__gte=0), name="inventory_position_subcontractor_nonnegative"),
        ]
        ordering = ("warehouse__name", "location__code", "product__name")

    def clean(self):
        super().clean()
        if self.warehouse_id and self.warehouse.organization_id != self.organization_id:
            raise ValidationError({"warehouse": "Warehouse is outside the position organization."})
        if self.location_id and self.location.warehouse_id != self.warehouse_id:
            raise ValidationError({"location": "Location must belong to the selected warehouse."})
        if self.product_id and self.product.organization_id != self.organization_id:
            raise ValidationError({"product": "Product is outside the position organization."})
        if self.product_variant_id and self.product_variant.product_id != self.product_id:
            raise ValidationError({"product_variant": "Variant must belong to the selected product."})
        if self.unit_id and self.unit.organization_id != self.organization_id:
            raise ValidationError({"unit": "Unit is outside the position organization."})
        if self.product_id and self.unit_id and self.product.unit.category != self.unit.category:
            raise ValidationError({"unit": "Unit category must match the product unit category."})


class StockLot(models.Model):
    class Kind(models.TextChoices):
        LOT = "lot", "Lot"
        ROLL = "roll", "Roll"
        REMNANT = "remnant", "Reusable remnant"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXHAUSTED = "exhausted", "Exhausted"
        BLOCKED = "blocked", "Blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="stock_lots")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="lots")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="lots")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="stock_lots")
    product_variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="stock_lots", null=True, blank=True)
    unit = models.ForeignKey("internationalization.UnitOfMeasure", on_delete=models.PROTECT, related_name="stock_lots")
    code = models.CharField(max_length=96)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.LOT)
    origin = models.CharField(max_length=255, blank=True)
    supplier_reference = models.CharField(max_length=160, blank=True)
    width = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    initial_length = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    remaining_length = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    initial_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    remaining_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    reusable = models.BooleanField(default=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("organization", "code"), name="inventory_lot_unique_code_org"),
            models.CheckConstraint(condition=models.Q(initial_quantity__gte=0), name="inventory_lot_initial_quantity_nonnegative"),
            models.CheckConstraint(condition=models.Q(remaining_quantity__gte=0), name="inventory_lot_remaining_quantity_nonnegative"),
            models.CheckConstraint(condition=models.Q(initial_length__isnull=True) | models.Q(initial_length__gte=0), name="inventory_lot_initial_length_nonnegative"),
            models.CheckConstraint(condition=models.Q(remaining_length__isnull=True) | models.Q(remaining_length__gte=0), name="inventory_lot_remaining_length_nonnegative"),
        ]
        ordering = ("code",)

    def clean(self):
        super().clean()
        if self.warehouse_id and self.warehouse.organization_id != self.organization_id:
            raise ValidationError({"warehouse": "Warehouse is outside the lot organization."})
        if self.location_id and self.location.warehouse_id != self.warehouse_id:
            raise ValidationError({"location": "Location must belong to the selected warehouse."})
        if self.product_id and self.product.organization_id != self.organization_id:
            raise ValidationError({"product": "Product is outside the lot organization."})
        if self.product_variant_id and self.product_variant.product_id != self.product_id:
            raise ValidationError({"product_variant": "Variant must belong to the selected product."})
        if self.unit_id and self.unit.organization_id != self.organization_id:
            raise ValidationError({"unit": "Unit is outside the lot organization."})
        if self.product_id and self.unit_id and self.product.unit.category != self.unit.category:
            raise ValidationError({"unit": "Unit category must match the product unit category."})
        if self.remaining_quantity > self.initial_quantity:
            raise ValidationError({"remaining_quantity": "Remaining quantity cannot exceed initial quantity."})
        if self.initial_length is not None and self.remaining_length is not None and self.remaining_length > self.initial_length:
            raise ValidationError({"remaining_length": "Remaining length cannot exceed initial length."})


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        RECEIPT = "receipt", "Receipt"
        ISSUE = "issue", "Issue"
        TRANSFER = "transfer", "Transfer"
        ADJUSTMENT_IN = "adjustment_in", "Adjustment in"
        ADJUSTMENT_OUT = "adjustment_out", "Adjustment out"
        RETURN_IN = "return_in", "Return in"
        PRODUCTION_OUTPUT = "production_output", "Production output"
        DAMAGE = "damage", "Mark damaged"
        RESTORE_DAMAGE = "restore_damage", "Restore damaged"
        PRODUCTION_CONSUMPTION = "production_consumption", "Production consumption"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="stock_movements")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="stock_movements")
    source_location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="outgoing_movements", null=True, blank=True)
    destination_location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="incoming_movements", null=True, blank=True)
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="stock_movements")
    product_variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="stock_movements", null=True, blank=True)
    unit = models.ForeignKey("internationalization.UnitOfMeasure", on_delete=models.PROTECT, related_name="stock_movements")
    lot = models.ForeignKey(StockLot, on_delete=models.PROTECT, related_name="movements", null=True, blank=True)
    movement_type = models.CharField(max_length=32, choices=MovementType.choices)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    reason = models.CharField(max_length=255, blank=True)
    reference_type = models.CharField(max_length=80, blank=True)
    reference_id = models.UUIDField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=160, blank=True)
    created_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="created_stock_movements", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="inventory_movement_positive_quantity"),
            models.UniqueConstraint(
                fields=("organization", "idempotency_key"),
                condition=~models.Q(idempotency_key=""),
                name="inventory_movement_unique_idempotency_org",
            ),
        ]
        ordering = ("-created_at", "-id")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Stock movements are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Stock movements are immutable.")


class StockReservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        IN_PRODUCTION = "in_production", "In production"
        RELEASED = "released", "Released"
        CONSUMED = "consumed", "Consumed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="stock_reservations")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="stock_reservations")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="reservations")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="reservations")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="stock_reservations")
    product_variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="stock_reservations", null=True, blank=True)
    unit = models.ForeignKey("internationalization.UnitOfMeasure", on_delete=models.PROTECT, related_name="stock_reservations")
    lot = models.ForeignKey(StockLot, on_delete=models.PROTECT, related_name="reservations", null=True, blank=True)
    order = models.ForeignKey("sales.Order", on_delete=models.PROTECT, related_name="stock_reservations", null=True, blank=True)
    production_order_id = models.UUIDField(null=True, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE)
    idempotency_key = models.CharField(max_length=160, blank=True)
    created_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="created_stock_reservations", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    released_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="inventory_reservation_positive_quantity"),
            models.UniqueConstraint(
                fields=("organization", "idempotency_key"),
                condition=~models.Q(idempotency_key=""),
                name="inventory_reservation_unique_idempotency_org",
            ),
        ]
        ordering = ("-created_at",)

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the reservation organization."})
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            raise ValidationError({"warehouse": "Warehouse is outside the reservation company."})
        if self.location_id and self.location.warehouse_id != self.warehouse_id:
            raise ValidationError({"location": "Location must belong to the reservation warehouse."})
        if self.product_id and self.product.organization_id != self.organization_id:
            raise ValidationError({"product": "Product is outside the reservation organization."})
        if self.product_variant_id and self.product_variant.product_id != self.product_id:
            raise ValidationError({"product_variant": "Variant must belong to the selected product."})
        if self.unit_id and self.unit.organization_id != self.organization_id:
            raise ValidationError({"unit": "Unit is outside the reservation organization."})
        if self.lot_id:
            if self.lot.product_id != self.product_id or self.lot.location_id != self.location_id:
                raise ValidationError({"lot": "Lot must match the reservation product and location."})
        if self.order_id and self.order.organization_id != self.organization_id:
            raise ValidationError({"order": "Order is outside the reservation organization."})
