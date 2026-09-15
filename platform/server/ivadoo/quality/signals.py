from django.db.models.signals import pre_save
from django.dispatch import receiver

from ivadoo.manufacturing.models import ManufacturingOperation, ManufacturingOrder
from ivadoo.purchases.models import PurchaseReceipt

from .services import assert_quality_gate_passed


@receiver(pre_save, sender=PurchaseReceipt)
def enforce_receipt_quality_gate(sender, instance, **kwargs):
    if not instance.pk or instance.status != PurchaseReceipt.Status.POSTED:
        return
    previous = sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    if previous == PurchaseReceipt.Status.POSTED:
        return
    for line in instance.lines.all().only("id"):
        assert_quality_gate_passed(purchase_receipt_line=line)


@receiver(pre_save, sender=ManufacturingOrder)
def enforce_manufacturing_output_quality_gate(sender, instance, **kwargs):
    if not instance.pk or instance.status != ManufacturingOrder.Status.DONE:
        return
    previous = sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    if previous == ManufacturingOrder.Status.DONE:
        return
    assert_quality_gate_passed(manufacturing_order=instance)
    for operation in instance.operations.all().only("id"):
        assert_quality_gate_passed(manufacturing_operation=operation)


@receiver(pre_save, sender=ManufacturingOperation)
def enforce_operation_sequence_quality_gate(sender, instance, **kwargs):
    if not instance.pk or instance.status != ManufacturingOperation.Status.IN_PROGRESS:
        return
    previous_status = sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    if previous_status == ManufacturingOperation.Status.IN_PROGRESS:
        return
    previous_operations = sender.objects.filter(
        manufacturing_order_id=instance.manufacturing_order_id,
        position__lt=instance.position,
        status=ManufacturingOperation.Status.DONE,
    ).only("id")
    for previous_operation in previous_operations:
        assert_quality_gate_passed(manufacturing_operation=previous_operation)
