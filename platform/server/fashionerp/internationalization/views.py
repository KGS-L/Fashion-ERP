from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from fashionerp.audit.services import audit_snapshot, record_audit_event
from fashionerp.authorization.services import (
    authorized_company_ids,
    authorized_establishment_ids,
)
from fashionerp.organizations.models import Company, Establishment

from .constants import SUPPORTED_LANGUAGES
from .models import Currency, ExchangeRate, UnitOfMeasure
from .permissions import CanAccessInternationalSettings
from .serializers import (
    CurrencySerializer,
    ExchangeRateSerializer,
    InternationalizationContextResponseSerializer,
    LanguageOptionSerializer,
    TranslationCatalogResponseSerializer,
    UnitOfMeasureSerializer,
)
from .services import (
    load_catalog,
    locale_direction,
    locale_formats,
    resolve_effective_language,
)


class LanguageListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: LanguageOptionSerializer(many=True)},
    )
    def get(self, request):
        return Response(
            [
                {
                    "code": code,
                    "name": name,
                    "direction": locale_direction(code),
                }
                for code, name in SUPPORTED_LANGUAGES
            ]
        )


class TranslationCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: TranslationCatalogResponseSerializer},
    )
    def get(self, request):
        requested = request.query_params.get("language")
        language_code = resolve_effective_language(
            user=request.user,
            requested=requested,
        )
        return Response(
            {
                "language": language_code,
                "direction": locale_direction(language_code),
                "catalog": load_catalog(language_code),
                "formats": locale_formats(language_code),
            }
        )


class InternationalizationContextView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: InternationalizationContextResponseSerializer},
    )
    def get(self, request):
        company = self._company(request)
        establishment = self._establishment(request, company=company)
        if company is None and establishment is not None:
            company = establishment.company
        language_code = resolve_effective_language(
            user=request.user,
            company=company,
            requested=request.query_params.get("language"),
        )

        functional_currency = None
        if company and company.functional_currency_id:
            functional_currency = CurrencySerializer(
                company.functional_currency
            ).data

        return Response(
            {
                "language": language_code,
                "direction": locale_direction(language_code),
                "formats": locale_formats(language_code),
                "functional_currency": functional_currency,
                "timezone": (
                    establishment.timezone
                    if establishment is not None
                    else "UTC"
                ),
                "company_id": str(company.id) if company else None,
                "establishment_id": (
                    str(establishment.id) if establishment else None
                ),
            }
        )

    def _company(self, request):
        company_id = request.query_params.get("company_id")
        if not company_id:
            return None
        allowed_ids = authorized_company_ids(
            request.user,
            "foundation.company.view",
        )
        try:
            return Company.objects.select_related(
                "functional_currency"
            ).get(
                organization_id=request.user.organization_id,
                id__in=allowed_ids,
                pk=company_id,
            )
        except (Company.DoesNotExist, ValueError) as exc:
            raise NotFound("Company not found.") from exc

    def _establishment(self, request, *, company=None):
        establishment_id = request.query_params.get("establishment_id")
        if not establishment_id:
            return None
        allowed_ids = authorized_establishment_ids(
            request.user,
            "foundation.establishment.view",
        )
        try:
            establishment = Establishment.objects.select_related(
                "company",
                "company__functional_currency",
            ).get(
                company__organization_id=request.user.organization_id,
                id__in=allowed_ids,
                pk=establishment_id,
            )
        except (Establishment.DoesNotExist, ValueError) as exc:
            raise NotFound("Establishment not found.") from exc

        if company is not None and establishment.company_id != company.id:
            raise ValidationError(
                {
                    "establishment_id": (
                        "Establishment does not belong to the selected company."
                    )
                }
            )
        return establishment


class CurrencyListCreateView(generics.ListCreateAPIView):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = [CanAccessInternationalSettings]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ("code", "name", "symbol")
    ordering_fields = ("code", "name")
    ordering = ("code",)

    def perform_create(self, serializer):
        with transaction.atomic():
            currency = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="i18n.currency.create",
                object_instance=currency,
                after=audit_snapshot(currency),
                request=self.request,
            )


class CurrencyDetailView(generics.RetrieveUpdateAPIView):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = [CanAccessInternationalSettings]
    lookup_field = "code"
    lookup_url_kwarg = "currency_code"

    def perform_update(self, serializer):
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            currency = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="i18n.currency.update",
                object_instance=currency,
                before=before,
                after=audit_snapshot(currency),
                request=self.request,
            )


class ExchangeRateListCreateView(generics.ListCreateAPIView):
    queryset = ExchangeRate.objects.none()
    serializer_class = ExchangeRateSerializer
    permission_classes = [CanAccessInternationalSettings]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = (
        "base_currency",
        "quote_currency",
        "valid_on",
    )
    ordering_fields = ("valid_on", "created_at")
    ordering = ("-valid_on",)

    def get_queryset(self):
        return ExchangeRate.objects.filter(
            organization_id=self.request.user.organization_id
        ).select_related("base_currency", "quote_currency")

    def perform_create(self, serializer):
        with transaction.atomic():
            rate = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="i18n.exchange_rate.create",
                object_instance=rate,
                after=audit_snapshot(rate),
                request=self.request,
            )


class ExchangeRateDetailView(generics.RetrieveUpdateAPIView):
    queryset = ExchangeRate.objects.none()
    serializer_class = ExchangeRateSerializer
    permission_classes = [CanAccessInternationalSettings]
    lookup_url_kwarg = "rate_id"

    def get_queryset(self):
        return ExchangeRate.objects.filter(
            organization_id=self.request.user.organization_id
        ).select_related("base_currency", "quote_currency")

    def perform_update(self, serializer):
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            rate = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="i18n.exchange_rate.update",
                object_instance=rate,
                before=before,
                after=audit_snapshot(rate),
                request=self.request,
            )


class UnitOfMeasureListCreateView(generics.ListCreateAPIView):
    queryset = UnitOfMeasure.objects.none()
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [CanAccessInternationalSettings]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ("category", "is_active")
    search_fields = ("code", "name", "symbol")
    ordering_fields = ("category", "name", "code")
    ordering = ("category", "name")

    def get_queryset(self):
        return UnitOfMeasure.objects.filter(
            organization_id=self.request.user.organization_id
        )

    def perform_create(self, serializer):
        with transaction.atomic():
            unit = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="i18n.unit.create",
                object_instance=unit,
                after=audit_snapshot(unit),
                request=self.request,
            )


class UnitOfMeasureDetailView(generics.RetrieveUpdateAPIView):
    queryset = UnitOfMeasure.objects.none()
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [CanAccessInternationalSettings]
    lookup_url_kwarg = "unit_id"

    def get_queryset(self):
        return UnitOfMeasure.objects.filter(
            organization_id=self.request.user.organization_id
        )

    def perform_update(self, serializer):
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            unit = serializer.save()
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="i18n.unit.update",
                object_instance=unit,
                before=before,
                after=audit_snapshot(unit),
                request=self.request,
            )

