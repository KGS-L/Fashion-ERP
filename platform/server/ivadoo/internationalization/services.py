import json
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.utils.formats import date_format, get_format, number_format
from django.utils.translation import override

from .constants import (
    DEFAULT_LANGUAGE_CODE,
    RTL_LANGUAGE_CODES,
    SUPPORTED_LANGUAGE_CODES,
)


CATALOG_DIR = Path(__file__).resolve().parent / "catalogs"


def normalize_language_code(language_code: str | None) -> str:
    if not language_code:
        return DEFAULT_LANGUAGE_CODE
    normalized = language_code.lower().split("-", 1)[0]
    if normalized not in SUPPORTED_LANGUAGE_CODES:
        return DEFAULT_LANGUAGE_CODE
    return normalized


@lru_cache(maxsize=None)
def load_catalog(language_code: str) -> dict:
    language_code = normalize_language_code(language_code)
    path = CATALOG_DIR / f"{language_code}.json"
    with path.open("r", encoding="utf-8") as catalog_file:
        return json.load(catalog_file)


def plural_category(language_code: str, count: int | Decimal) -> str:
    language_code = normalize_language_code(language_code)
    numeric = Decimal(str(count))

    if language_code == "ar":
        if numeric != numeric.to_integral_value():
            return "other"
        integer = int(numeric)
        if integer == 0:
            return "zero"
        if integer == 1:
            return "one"
        if integer == 2:
            return "two"
        mod100 = integer % 100
        if 3 <= mod100 <= 10:
            return "few"
        if 11 <= mod100 <= 99:
            return "many"
        return "other"

    if language_code in {"fr", "pt"}:
        return "one" if numeric in {Decimal("0"), Decimal("1")} else "other"

    return "one" if numeric == 1 else "other"


def translate_key(
    key: str,
    *,
    language_code: str | None = None,
    count: int | Decimal | None = None,
) -> str:
    language_code = normalize_language_code(language_code)
    catalog = load_catalog(language_code)
    value = catalog.get(key)

    if value is None and language_code != DEFAULT_LANGUAGE_CODE:
        value = load_catalog(DEFAULT_LANGUAGE_CODE).get(key)

    if value is None:
        return key

    if isinstance(value, dict):
        category = plural_category(language_code, count or 0)
        template = value.get(category) or value.get("other")
        if template is None:
            return key
        return template.format(count=count or 0)

    return str(value)


def locale_formats(language_code: str | None) -> dict:
    language_code = normalize_language_code(language_code)
    return {
        "date": get_format("DATE_FORMAT", lang=language_code),
        "short_date": get_format("SHORT_DATE_FORMAT", lang=language_code),
        "datetime": get_format("DATETIME_FORMAT", lang=language_code),
        "short_datetime": get_format(
            "SHORT_DATETIME_FORMAT",
            lang=language_code,
        ),
        "decimal_separator": get_format(
            "DECIMAL_SEPARATOR",
            lang=language_code,
        ),
        "thousand_separator": get_format(
            "THOUSAND_SEPARATOR",
            lang=language_code,
        ),
        "number_grouping": get_format(
            "NUMBER_GROUPING",
            lang=language_code,
        ),
        "first_day_of_week": get_format(
            "FIRST_DAY_OF_WEEK",
            lang=language_code,
        ),
    }


def format_number(
    value,
    *,
    language_code: str | None = None,
    decimal_places: int | None = None,
) -> str:
    language_code = normalize_language_code(language_code)
    with override(language_code):
        return number_format(
            value,
            decimal_pos=decimal_places,
            use_l10n=True,
            force_grouping=True,
        )


def format_date(
    value: date,
    *,
    language_code: str | None = None,
    short: bool = True,
) -> str:
    language_code = normalize_language_code(language_code)
    with override(language_code):
        return date_format(
            value,
            format=(
                "SHORT_DATE_FORMAT"
                if short
                else "DATE_FORMAT"
            ),
            use_l10n=True,
        )


def resolve_effective_language(*, user=None, company=None, requested=None) -> str:
    if requested:
        normalized = normalize_language_code(requested)
        if normalized == requested.lower().split("-", 1)[0]:
            return normalized
    if user is not None and getattr(user, "language_code", ""):
        return normalize_language_code(user.language_code)
    if company is not None and getattr(company, "language_code", ""):
        return normalize_language_code(company.language_code)
    return normalize_language_code(settings.LANGUAGE_CODE)


def locale_direction(language_code: str | None) -> str:
    return (
        "rtl"
        if normalize_language_code(language_code) in RTL_LANGUAGE_CODES
        else "ltr"
    )
