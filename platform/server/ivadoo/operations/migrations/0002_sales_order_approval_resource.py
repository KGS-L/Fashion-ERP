from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("operations", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="approvalrule",
            name="resource",
            field=models.CharField(
                choices=[
                    ("purchase_order", "Purchase order"),
                    ("stock_movement", "Stock movement"),
                    ("sales_order", "Sales order"),
                ],
                max_length=32,
            ),
        ),
    ]
