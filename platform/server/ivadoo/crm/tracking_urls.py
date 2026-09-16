from django.urls import path

from .tracking_views import (
    CRMFollowUpDetailView,
    CRMFollowUpListView,
    CRMInteractionListView,
    CRMSegmentDetailView,
    CRMSegmentListView,
    CRMSegmentMembershipDetailView,
    CRMSegmentMembershipListView,
)


urlpatterns = [
    path("segments/", CRMSegmentListView.as_view(), name="segment-list"),
    path("segments/<uuid:segment_id>/", CRMSegmentDetailView.as_view(), name="segment-detail"),
    path(
        "segment-memberships/",
        CRMSegmentMembershipListView.as_view(),
        name="segment-membership-list",
    ),
    path(
        "segment-memberships/<uuid:membership_id>/",
        CRMSegmentMembershipDetailView.as_view(),
        name="segment-membership-detail",
    ),
    path("followups/", CRMFollowUpListView.as_view(), name="followup-list"),
    path("followups/<uuid:followup_id>/", CRMFollowUpDetailView.as_view(), name="followup-detail"),
    path("interactions/", CRMInteractionListView.as_view(), name="interaction-list"),
]
