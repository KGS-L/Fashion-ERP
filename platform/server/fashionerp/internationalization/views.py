from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
    UnitOfMeasureSerializer,
)
from .services import (
    load_catalog,
    locale_direction,
    locale_formats,
    normalize_language_code,
    resolve_effective_language,
)


class LanguageListView(APIView):
    permission_classes = [IsAuthenticated]

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

    def get(self, request):
        company = self._company(request)
        establishment = self._establishment(request, company=company)
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


class CurrencyDetailView(generics.RetrieveUpdateAPIView):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = [CanAccessInternationalSettings]
    lookup_field = "code"
    lookup_url_kwarg = "currency_code"


class ExchangeRateListCreateView(generics.ListCreateAPIView):
    serializer_class = ExchangeRateSerializer
    permission_classes = [CanAccessInternationalSettings]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = (
        "base_currency_id",
        "quote_currency_id",
        "valid_on",
    )
    ordering_fields = ("valid_on", "created_at")
    ordering = ("-valid_on",)

    def get_queryset(self):
        return ExchangeRate.objects.filter(
            organization_id=self.request.user.organization_id
        ).select_related("base_currency", "quote_currency")


class ExchangeRateDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ExchangeRateSerializer
    permission_classes = [CanAccessInternationalSettings]
    lookup_url_kwarg = "rate_id"

    def get_queryset(self):
        return ExchangeRate.objects.filter(
            organization_id=self.request.user.organization_id
        ).select_related("base_currency", "quote_currency")


class UnitOfMeasureListCreateView(generics.ListCreateAPIView):
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


class UnitOfMeasureDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [CanAccessInternationalSettings]
    lookup_url_kwarg = "unit_id"

    def get_queryset(self):
        return UnitOfMeasure.objects.filter(
            organization_id=self.request.user.organization_id
        )
