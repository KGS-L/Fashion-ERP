from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .custom_fields import validate_custom_field_definition
from .models import CustomFieldDefinition


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
        try:
            validate_custom_field_definition(
                organization=request.user.organization,
                model_key=model_key,
                key=key,
                field_type=field_type,
                options=options,
                validation=validation,
            )
        except (DjangoValidationError, LookupError) as exc:
            if isinstance(exc, DjangoValidationError) and hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict) from exc
            raise serializers.ValidationError({"model_key": str(exc)}) from exc
        if instance and (model_key != instance.model_key or key != instance.key):
            raise serializers.ValidationError(
                {"key": "The model/key identity of a published custom field cannot be changed."}
            )
        return attrs
