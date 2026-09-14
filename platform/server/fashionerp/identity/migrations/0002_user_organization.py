import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="organizations.organization",
            ),
        ),
    ]
