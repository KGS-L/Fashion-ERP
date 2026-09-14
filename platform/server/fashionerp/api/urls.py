from django.urls import include, path


app_name = "api_v1"

urlpatterns = [
    path("auth/", include("fashionerp.identity.urls")),
]
