from django.urls import path

from .views import (
    CRMConversionEventListView,
    CRMLeadConvertView,
    CRMLeadDetailView,
    CRMLeadListView,
    CRMOpportunityConvertView,
    CRMOpportunityDetailView,
    CRMOpportunityListView,
    CRMPipelineStageDetailView,
    CRMPipelineStageListView,
    CRMSourceDetailView,
    CRMSourceListView,
)


app_name = "crm"

urlpatterns = [
    path("sources/", CRMSourceListView.as_view(), name="source-list"),
    path("sources/<uuid:source_id>/", CRMSourceDetailView.as_view(), name="source-detail"),
    path("stages/", CRMPipelineStageListView.as_view(), name="stage-list"),
    path("stages/<uuid:stage_id>/", CRMPipelineStageDetailView.as_view(), name="stage-detail"),
    path("leads/", CRMLeadListView.as_view(), name="lead-list"),
    path("leads/<uuid:lead_id>/", CRMLeadDetailView.as_view(), name="lead-detail"),
    path(
        "leads/<uuid:lead_id>/actions/convert/",
        CRMLeadConvertView.as_view(),
        name="lead-convert",
    ),
    path("opportunities/", CRMOpportunityListView.as_view(), name="opportunity-list"),
    path(
        "opportunities/<uuid:opportunity_id>/",
        CRMOpportunityDetailView.as_view(),
        name="opportunity-detail",
    ),
    path(
        "opportunities/<uuid:opportunity_id>/actions/convert/",
        CRMOpportunityConvertView.as_view(),
        name="opportunity-convert",
    ),
    path("conversions/", CRMConversionEventListView.as_view(), name="conversion-list"),
]
