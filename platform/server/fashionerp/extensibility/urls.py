from django.urls import path

from .views import ModuleActionView, ModuleDetailView, ModuleListView


app_name = "extensibility"

urlpatterns = [
    path("modules/", ModuleListView.as_view(), name="module-list"),
    path("modules/<str:module_code>/", ModuleDetailView.as_view(), name="module-detail"),
    path(
        "modules/<str:module_code>/<str:action>/",
        ModuleActionView.as_view(),
        name="module-action",
    ),
]
