import uuid

from django.db import models


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
