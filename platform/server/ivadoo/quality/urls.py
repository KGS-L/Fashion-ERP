from django.urls import path

from .views import (
    QualityInspectionCompleteView,
    QualityInspectionDetailView,
    QualityInspectionListCreateView,
    QualityReworkCompleteView,
    QualityReworkListView,
    QualitySummaryView,
)


app_name = "quality"

urlpatterns = [
    path("inspections/", QualityInspectionListCreateView.as_view(), name="inspection-list"),
    path("inspections/<uuid:inspection_id>/", QualityInspectionDetailView.as_view(), name="inspection-detail"),
    path("inspections/<uuid:inspection_id>/complete/", QualityInspectionCompleteView.as_view(), name="inspection-complete"),
    path("reworks/", QualityReworkListView.as_view(), name="rework-list"),
    path("reworks/<uuid:rework_id>/complete/", QualityReworkCompleteView.as_view(), name="rework-complete"),
    path("summary/", QualitySummaryView.as_view(), name="summary"),
]
