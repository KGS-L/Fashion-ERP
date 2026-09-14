from django.urls import path

from .views import (
    CurrencyDetailView,
    CurrencyListCreateView,
    ExchangeRateDetailView,
    ExchangeRateListCreateView,
    InternationalizationContextView,
    LanguageListView,
    TranslationCatalogView,
    UnitOfMeasureDetailView,
    UnitOfMeasureListCreateView,
)


app_name = "internationalization"

urlpatterns = [
    path("languages/", LanguageListView.as_view(), name="language-list"),
    path("catalog/", TranslationCatalogView.as_view(), name="catalog"),
    path(
        "context/",
        InternationalizationContextView.as_view(),
        name="context",
    ),
    path(
        "currencies/",
        CurrencyListCreateView.as_view(),
        name="currency-list",
    ),
    path(
        "currencies/<str:currency_code>/",
        CurrencyDetailView.as_view(),
        name="currency-detail",
    ),
    path(
        "exchange-rates/",
        ExchangeRateListCreateView.as_view(),
        name="exchange-rate-list",
    ),
    path(
        "exchange-rates/<uuid:rate_id>/",
        ExchangeRateDetailView.as_view(),
        name="exchange-rate-detail",
    ),
    path(
        "units/",
        UnitOfMeasureListCreateView.as_view(),
        name="unit-list",
    ),
    path(
        "units/<uuid:unit_id>/",
        UnitOfMeasureDetailView.as_view(),
        name="unit-detail",
    ),
]
