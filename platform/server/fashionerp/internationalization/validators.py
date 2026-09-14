from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError

from .constants import SUPPORTED_LANGUAGE_CODES


def validate_language_code(value: str) -> None:
    if value not in SUPPORTED_LANGUAGE_CODES:
        raise ValidationError("Unsupported FashionERP language code.")


def validate_timezone_name(value: str) -> None:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError("Invalid IANA timezone name.") from exc
