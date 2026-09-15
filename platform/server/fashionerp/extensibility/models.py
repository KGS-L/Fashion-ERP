import uuid

from django.core.validators import RegexValidator
from django.db import models


custom_field_key_validator = RegexValidator(
    regex=r"^x_[a-z][a-z0-9_]{1,61}$",
    message="Custom field keys must start with x_ and use lowercase letters, numbers and underscores.",
)


class ModuleInstallation(models.Model):
    class State(models.TextChoices):
        INSTALLED = "installed", "Installed"
        ENABLED = "enabled", "Enabled"
        DISABLED = "disabled", "Disabled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="module_installations",
    )
    module_code = models.CharField(max_length=120)
    installed_version = models.CharField(max_length=32)
    state = models.CharField(
        max_length=16,
        choices=State.choices,
        default=State.INSTALLED,
    )
    last_changed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="module_installation_changes",
        null=True,
        blank=True,
    )
    installed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "module_code"),
                name="extensibility_unique_module_installation",
            )
        ]
        ordering = ("module_code",)

    def __str__(self):
        return f"{self.module_code}@{self.installed_version} ({self.state})"


class CustomFieldDefinition(models.Model):
    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        LONG_TEXT = "long_text", "Long text"
        INTEGER = "integer", "Integer"
        DECIMAL = "decimal", "Decimal"
        BOOLEAN = "boolean", "Boolean"
        DATE = "date", "Date"
        DATETIME = "datetime", "Datetime"
        SELECTION = "selection", "Selection"
        MULTI_SELECTION = "multi_selection", "Multi selection"
        REFERENCE = "reference", "Reference"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="custom_field_definitions",
    )
    model_key = models.CharField(max_length=160)
    key = models.CharField(max_length=64, validators=[custom_field_key_validator])
    label = models.CharField(max_length=160)
    field_type = models.CharField(max_length=24, choices=FieldType.choices)
    required = models.BooleanField(default=False)
    default_value = models.JSONField(null=True, blank=True)
    options = models.JSONField(default=list, blank=True)
    validation = models.JSONField(default=dict, blank=True)
    view_permission = models.CharField(max_length=160, blank=True)
    edit_permission = models.CharField(max_length=160, blank=True)
    is_sensitive = models.BooleanField(default=False)
    is_searchable = models.BooleanField(default=False)
    is_reportable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_custom_fields",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "model_key", "key"),
                name="extensibility_unique_custom_field",
            )
        ]
        indexes = [
            models.Index(
                fields=("organization", "model_key", "is_active"),
                name="ext_custom_field_lookup",
            )
        ]
        ordering = ("model_key", "key")

    def __str__(self):
        return f"{self.model_key}.{self.key}"


class CustomObjectData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="custom_object_data",
    )
    model_key = models.CharField(max_length=160)
    object_id = models.UUIDField()
    values = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=0)
    updated_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="updated_custom_object_data",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "model_key", "object_id"),
                name="extensibility_unique_custom_object_data",
            )
        ]
        indexes = [
            models.Index(
                fields=("organization", "model_key", "object_id"),
                name="ext_custom_object_lookup",
            )
        ]

    def __str__(self):
        return f"{self.model_key}:{self.object_id}"
