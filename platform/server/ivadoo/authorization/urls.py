from django.urls import path

from .views import (
    AccessUserDetailView,
    AccessUserListView,
    AccessUserTwoFactorResetView,
    GrantListCreateView,
    GrantRevokeView,
    GroupDetailView,
    GroupListCreateView,
    PermissionListView,
    RoleDetailView,
    RoleListCreateView,
)


app_name = "authorization"

urlpatterns = [
    path("permissions/", PermissionListView.as_view(), name="permission-list"),
    path("roles/", RoleListCreateView.as_view(), name="role-list"),
    path("roles/<uuid:role_id>/", RoleDetailView.as_view(), name="role-detail"),
    path("groups/", GroupListCreateView.as_view(), name="group-list"),
    path(
        "groups/<uuid:group_id>/",
        GroupDetailView.as_view(),
        name="group-detail",
    ),
    path("grants/", GrantListCreateView.as_view(), name="grant-list"),
    path(
        "grants/<uuid:grant_id>/revoke/",
        GrantRevokeView.as_view(),
        name="grant-revoke",
    ),
    path("users/", AccessUserListView.as_view(), name="user-list"),
    path("users/<uuid:user_id>/", AccessUserDetailView.as_view(), name="user-detail"),
    path(
        "users/<uuid:user_id>/2fa/reset/",
        AccessUserTwoFactorResetView.as_view(),
        name="user-two-factor-reset",
    ),
]
