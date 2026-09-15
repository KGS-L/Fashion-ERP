from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from fashionerp.internationalization.models import Currency
from fashionerp.organizations.models import Company, Establishment

from .models import Customer, CustomerAddress, CustomerConsent, CustomerContact


class CustomerContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerContact
        fields = ("id", "contact_type", "label", "value", "is_primary", "created_at")
        read_only_fields = ("id", "created_at")


class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = (
            "id", "address_type", "label", "address_line1", "address_line2",
            "city", "region", "postal_code", "country_code", "is_primary", "created_at",
        )
        read_only_fields = ("id", "created_at")


class CustomerConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerConsent
        fields = ("id", "consent_type", "granted", "recorded_at", "source", "note")
        read_only_fields = ("id", "recorded_at")


class CustomerSerializer(serializers.ModelSerializer):
    status = extend_schema_field(
        {"type": "string", "enum": ["active", "inactive", "archived"]}
    )(serializers.ChoiceField(choices=Customer.CustomerStatus.choices, required=False))
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )
    establishment_id = serializers.PrimaryKeyRelatedField(
        source="establishment",
        queryset=Establishment.objects.all(),
        allow_null=True,
        required=False,
    )
    preferred_currency_id = serializers.PrimaryKeyRelatedField(
        source="preferred_currency",
        queryset=Currency.objects.filter(is_active=True),
        allow_null=True,
        required=False,
    )
    contacts = CustomerContactSerializer(many=True, required=False)
    addresses = CustomerAddressSerializer(many=True, required=False)
    consents = CustomerConsentSerializer(many=True, required=False)

    class Meta:
        model = Customer
        fields = (
            "id", "organization_id", "company_id", "establishment_id",
            "customer_type", "code", "display_name", "first_name", "last_name",
            "legal_name", "email", "phone", "language_code",
            "preferred_currency_id", "preferences", "notes", "status",
            "contacts", "addresses", "consents", "created_at", "updated_at",
            "archived_at",
        )
        read_only_fields = (
            "id", "organization_id", "created_at", "updated_at", "archived_at",
        )

    def validate(self, attrs):
        company = attrs.get("company", getattr(self.instance, "company", None))
        establishment = attrs.get(
            "establishment", getattr(self.instance, "establishment", None)
        )
        request = self.context.get("request")
        if request and company and company.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"company_id": "Company is outside the local organization."}
            )
        if establishment and company and establishment.company_id != company.id:
            raise serializers.ValidationError(
                {"establishment_id": "Establishment must belong to the selected company."}
            )
        if self.instance and company and company.id != self.instance.company_id:
            raise serializers.ValidationError(
                {"company_id": "Moving a customer to another company is not supported."}
            )
        return attrs

    def create(self, validated_data):
        contacts = validated_data.pop("contacts", [])
        addresses = validated_data.pop("addresses", [])
        consents = validated_data.pop("consents", [])
        customer = Customer.objects.create(**validated_data)
        CustomerContact.objects.bulk_create(
            [CustomerContact(customer=customer, **item) for item in contacts]
        )
        CustomerAddress.objects.bulk_create(
            [CustomerAddress(customer=customer, **item) for item in addresses]
        )
        CustomerConsent.objects.bulk_create(
            [CustomerConsent(customer=customer, **item) for item in consents]
        )
        return customer

    def update(self, instance, validated_data):
        # Child collections have their own identity/history. Phase 2 does not
        # replace them implicitly during a customer master-data PATCH.
        validated_data.pop("contacts", None)
        validated_data.pop("addresses", None)
        validated_data.pop("consents", None)
        return super().update(instance, validated_data)
