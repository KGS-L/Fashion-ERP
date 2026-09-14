SUPPORTED_LANGUAGES = (
    ("fr", "Français"),
    ("en", "English"),
    ("es", "Español"),
    ("pt", "Português"),
    ("ar", "العربية"),
)

SUPPORTED_LANGUAGE_CODES = frozenset(code for code, _ in SUPPORTED_LANGUAGES)
DEFAULT_LANGUAGE_CODE = "fr"
RTL_LANGUAGE_CODES = frozenset({"ar"})
