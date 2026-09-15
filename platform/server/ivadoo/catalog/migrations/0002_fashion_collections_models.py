import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
        ("organizations", "0003_international_settings"),
    ]
    operations = [
        migrations.CreateModel(name="Season", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("code", models.SlugField(max_length=80)), ("name", models.CharField(max_length=160)),
            ("year", models.PositiveSmallIntegerField(blank=True, null=True)),
            ("start_date", models.DateField(blank=True, null=True)), ("end_date", models.DateField(blank=True, null=True)),
            ("is_active", models.BooleanField(default=True)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fashion_seasons", to="organizations.organization")),
        ], options={"ordering": ("-year", "name")}),
        migrations.CreateModel(name="Collection", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("code", models.SlugField(max_length=80)), ("name", models.CharField(max_length=200)),
            ("description", models.TextField(blank=True)), ("media_references", models.JSONField(blank=True, default=list)),
            ("is_active", models.BooleanField(default=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("company", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="fashion_collections", to="organizations.company")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fashion_collections", to="organizations.organization")),
            ("season", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="collections", to="catalog.season")),
        ], options={"ordering": ("name",)}),
        migrations.CreateModel(name="FashionModel", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("code", models.CharField(max_length=80)), ("name", models.CharField(max_length=255)),
            ("description", models.TextField(blank=True)), ("instructions", models.TextField(blank=True)),
            ("media_references", models.JSONField(blank=True, default=list)), ("metadata", models.JSONField(blank=True, default=dict)),
            ("is_active", models.BooleanField(default=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("collection", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="models", to="catalog.collection")),
            ("company", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="fashion_models", to="organizations.company")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fashion_models", to="organizations.organization")),
        ], options={"ordering": ("name",)}),
        migrations.CreateModel(name="FashionModelVariant", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("code", models.CharField(max_length=96)), ("color", models.CharField(blank=True, max_length=120)),
            ("size", models.CharField(blank=True, max_length=80)), ("instructions", models.TextField(blank=True)),
            ("media_references", models.JSONField(blank=True, default=list)), ("metadata", models.JSONField(blank=True, default=dict)),
            ("is_active", models.BooleanField(default=True)),
            ("fashion_model", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="variants", to="catalog.fashionmodel")),
        ], options={"ordering": ("code",)}),
        migrations.AddConstraint(model_name="season", constraint=models.UniqueConstraint(fields=("organization","code"), name="fashion_season_unique_code_per_org")),
        migrations.AddConstraint(model_name="collection", constraint=models.UniqueConstraint(fields=("organization","code"), name="fashion_collection_unique_code_per_org")),
        migrations.AddConstraint(model_name="fashionmodel", constraint=models.UniqueConstraint(fields=("organization","code"), name="fashion_model_unique_code_per_org")),
        migrations.AddConstraint(model_name="fashionmodelvariant", constraint=models.UniqueConstraint(fields=("fashion_model","code"), name="fashion_model_variant_unique_code")),
    ]
