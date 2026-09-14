from django.urls import include, path


app_name = "api_v1"

urlpatterns = [
    path("auth/", include("fashionerp.identity.urls")),
    path("organizations/", include("fashionerp.organizations.urls")),
    path("access/", include("fashionerp.authorization.urls")),
    path("audit/", include("fashionerp.audit.urls")),
    path("companies/", include("fashionerp.organizations.company_urls")),
    path(
        "establishments/",
        include("fashionerp.organizations.establishment_urls"),
    ),
]
