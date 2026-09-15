from django.urls import path

from .data_views import DataExportView, DataImportView
from .views import (
    CustomFieldDetailView,
    CustomFieldListCreateView,
    CustomObjectDataView,
    MetadataModelDetailView,
    MetadataModelListView,
    ModuleActionView,
    ModuleDetailView,
    ModuleListView,
)


app_name = "extensibility"

urlpatterns = [
    path("modules/", ModuleListView.as_view(), name="module-list"),
    path("modules/<str:module_code>/", ModuleDetailView.as_view(), name="module-detail"),
    path("modules/<str:module_code>/<str:action>/", ModuleActionView.as_view(), name="module-action"),
    path("custom-fields/", CustomFieldListCreateView.as_view(), name="custom-field-list"),
    path("custom-fields/<uuid:field_id>/", CustomFieldDetailView.as_view(), name="custom-field-detail"),
    path("custom-data/<str:model_key>/<uuid:object_id>/", CustomObjectDataView.as_view(), name="custom-data-detail"),
    path("metadata/models/", MetadataModelListView.as_view(), name="metadata-model-list"),
    path("metadata/models/<str:model_key>/", MetadataModelDetailView.as_view(), name="metadata-model-detail"),
    path("data/import/", DataImportView.as_view(), name="data-import"),
    path("data/export/", DataExportView.as_view(), name="data-export"),
]
