from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("extensibility", "0002_custom_fields")]

    operations = [
        migrations.AddField(
            model_name="customfielddefinition",
            name="edit_permission",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="customfielddefinition",
            name="is_sensitive",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="customfielddefinition",
            name="view_permission",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AlterField(
            model_name="customobjectdata",
            name="version",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
