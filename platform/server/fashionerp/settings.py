import os
from pathlib import Path

from django.utils.translation import gettext_lazy as _


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() in {"1", "true", "yes", "on"}

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "fashionerp.identity.apps.IdentityConfig",
    "fashionerp.organizations.apps.OrganizationsConfig",
    "fashionerp.authorization.apps.AuthorizationConfig",
    "fashionerp.audit.apps.AuditConfig",
    "fashionerp.internationalization.apps.InternationalizationConfig",
    "fashionerp.customers.apps.CustomersConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "fashionerp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "fashionerp.wsgi.application"
ASGI_APPLICATION = "fashionerp.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "fashionerp"),
        "USER": os.getenv("POSTGRES_USER", "fashionerp"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "60")),
    }
}

tenant_b_database = os.getenv("POSTGRES_TENANT_B_DB")
if tenant_b_database:
    DATABASES["tenant_b"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": tenant_b_database,
        "USER": os.getenv("POSTGRES_USER", "fashionerp"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 0,
    }

AUTH_USER_MODEL = "identity.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = os.getenv("DJANGO_LANGUAGE_CODE", "fr")
LANGUAGES = [
    ("fr", _("French")),
    ("en", _("English")),
    ("es", _("Spanish")),
    ("pt", _("Portuguese")),
    ("ar", _("Arabic")),
]
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

FASHIONERP_SESSION_ABSOLUTE_TTL_SECONDS = int(
    os.getenv("FASHIONERP_SESSION_ABSOLUTE_TTL_SECONDS", str(30 * 24 * 60 * 60))
)
FASHIONERP_SESSION_IDLE_TTL_SECONDS = int(
    os.getenv("FASHIONERP_SESSION_IDLE_TTL_SECONDS", str(12 * 60 * 60))
)
FASHIONERP_2FA_ENCRYPTION_KEY = os.environ["FASHIONERP_2FA_ENCRYPTION_KEY"]
FASHIONERP_TOTP_ISSUER = os.getenv("FASHIONERP_TOTP_ISSUER", "FashionERP")

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "fashionerp.api.pagination.StandardPageNumberPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "fashionerp.identity.authentication.OpaqueBearerAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": os.getenv("FASHIONERP_LOGIN_THROTTLE_RATE", "10/min"),
    },
    "EXCEPTION_HANDLER": "fashionerp.api.exceptions.fashionerp_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "FashionERP API",
    "DESCRIPTION": "Versioned REST API for the FashionERP platform.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
    },
}
