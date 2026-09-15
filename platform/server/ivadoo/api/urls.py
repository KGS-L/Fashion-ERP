from django.urls import include, path


app_name = "api_v1"

urlpatterns = [
    path("auth/", include("ivadoo.identity.urls")),
    path("organizations/", include("ivadoo.organizations.urls")),
    path("access/", include("ivadoo.authorization.urls")),
    path("audit/", include("ivadoo.audit.urls")),
    path("i18n/", include("ivadoo.internationalization.urls")),
    path("platform/", include("ivadoo.extensibility.urls")),
    path("companies/", include("ivadoo.organizations.company_urls")),
    path("customers/", include("ivadoo.customers.urls")),
    path("measurements/", include("ivadoo.measurements.urls")),
    path("products/", include("ivadoo.catalog.urls")),
    path("sales/", include("ivadoo.sales.urls")),
    path("inventory/", include("ivadoo.inventory.urls")),
    path(
        "establishments/",
        include("ivadoo.organizations.establishment_urls"),
    ),
]
