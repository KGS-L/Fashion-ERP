import django.db.models.deletion
from django.db import migrations, models

import ivadoo.internationalization.validators


class Migration(migrations.Migration):
    dependencies = [
        ("internationalization", "0001_initial"),
        ("organizations", "0002_company_establishment"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="functional_currency",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="functional_currency_companies",
                to="internationalization.currency",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="language_code",
            field=models.CharField(
                choices=[
                    ("fr", "Français"),
                    ("en", "English"),
                    ("es", "Español"),
                    ("pt", "Português"),
                    ("ar", "العربية"),
                ],
                default="fr",
                max_length=8,
                validators=[
                    ivadoo.internationalization.validators.validate_language_code
                ],
            ),
        ),
        migrations.AddField(
            model_name="establishment",
            name="timezone",
            field=models.CharField(
                default="UTC",
                max_length=64,
                validators=[
                    ivadoo.internationalization.validators.validate_timezone_name
                ],
            ),
        ),
    ]
