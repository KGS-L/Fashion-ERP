from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales", "0002_fittings_alterations_customer_validation")]

    operations = [
        migrations.AddConstraint(
            model_name="quotationline",
            constraint=models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="quotation_line_positive_quantity",
            ),
        ),
        migrations.AddConstraint(
            model_name="quotationline",
            constraint=models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="quotation_line_nonnegative_unit_price",
            ),
        ),
        migrations.AddConstraint(
            model_name="quotationline",
            constraint=models.CheckConstraint(
                condition=models.Q(discount_rate__gte=0) & models.Q(discount_rate__lte=1),
                name="quotation_line_discount_rate_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="orderline",
            constraint=models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="order_line_positive_quantity",
            ),
        ),
        migrations.AddConstraint(
            model_name="orderline",
            constraint=models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="order_line_nonnegative_unit_price",
            ),
        ),
    ]
