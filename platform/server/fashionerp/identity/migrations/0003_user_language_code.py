from django.db import migrations, models

import fashionerp.internationalization.validators


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0002_user_organization"),
        ("organizations", "0003_international_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
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
                    fashionerp.internationalization.validators.validate_language_code
                ],
            ),
        ),
    ]
