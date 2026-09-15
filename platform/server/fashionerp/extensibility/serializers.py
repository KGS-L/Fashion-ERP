from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .custom_fields import validate_custom_field_definition
from .models import CustomFieldDefinition, CustomObjectData


class CustomFieldDefinitionSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    created_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CustomFieldDefinition
        fields = (
            "id",
            "organization_id",
            "model_key",
            "key",
            "label",
            "field_type",
            "required",
            "default_value",
            "options",
            "validation",
            "view_permission",
            "edit_permission",
            "is_sensitive",
            "is_searchable",
            "is_reportable",
            "is_active",
            "version",
            "created_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "version",
            "created_by_id",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        request = self.context["request"]
        instance = self.instance
        model_key = attrs.get("model_key", getattr(instance, "model_key", None))
        key = attrs.get("key", getattr(instance, "key", None))
        field_type = attrs.get("field_type", getattr(instance, "field_type", None))
        options = attrs.get("options", getattr(instance, "options", []))
        validation = attrs.get("validation", getattr(instance, "validation", {}))
        view_permission = attrs.get("view_permission", getattr(instance, "view_permission", ""))
        edit_permission = attrs.get("edit_permission", getattr(instance, "edit_permission", ""))
        is_sensitive = attrs.get("is_sensitive", getattr(instance, "is_sensitive", False))
        try:
            validate_custom_field_definition(
                organization=request.user.organization,
                model_key=model_key,
                key=key,
                field_type=field_type,
                options=options,
                validation=validation,
                view_permission=view_permission,
                edit_permission=edit_permission,
                is_sensitive=is_sensitive,
            )
        except (DjangoValidationError, LookupError) as exc:
            if isinstance(exc, DjangoValidationError) and hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict) from exc
            raise serializers.ValidationError({"model_key": str(exc)}) from exc
        if instance and (model_key != instance.model_key or key != instance.key):
            raise serializers.ValidationError(
                {"key": "The model/key identity of a published custom field cannot be changed."}
            )
        if instance and field_type != instance.field_type:
            in_use = CustomObjectData.objects.filter(
                organization=instance.organization,
                model_key=instance.model_key,
                values__has_key=instance.key,
            ).exists()
            if in_use:
                raise serializers.ValidationError(
                    {"field_type": "A custom field type cannot change after values have been stored."}
                )
        return attrs


class ModuleStateSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    version = serializers.CharField()
    available_version = serializers.CharField()
    state = serializers.CharField()
    enabled = serializers.BooleanField()
    required = serializers.BooleanField()
    default_enabled = serializers.BooleanField()
    edition = serializers.CharField()
    dependencies = serializers.ListField(child=serializers.CharField())


class CustomDataWriteSerializer(serializers.Serializer):
    values = serializers.JSONField()


class CustomDataResponseSerializer(serializers.Serializer):
    model_key = serializers.CharField()
    object_id = serializers.UUIDField()
    version = serializers.IntegerField(required=False)
    values = serializers.JSONField()


class MetadataFieldSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    type = serializers.CharField()
    native = serializers.BooleanField()
    custom = serializers.BooleanField()
    protected = serializers.BooleanField()
    required = serializers.BooleanField()
    read_only = serializers.BooleanField()
    choices = serializers.JSONField(required=False)
    searchable = serializers.BooleanField(required=False)
    reportable = serializers.BooleanField(required=False)
    sensitive = serializers.BooleanField(required=False)
    version = serializers.IntegerField(required=False)
    reference_model = serializers.CharField(required=False, allow_null=True)


class MetadataModelSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    module = serializers.JSONField()
    permissions = serializers.JSONField()
    capabilities = serializers.JSONField()
    actions = serializers.ListField(child=serializers.CharField())
    fields = MetadataFieldSerializer(many=True)


class MetadataModelListSerializer(serializers.Serializer):
    models = MetadataModelSerializer(many=True)
