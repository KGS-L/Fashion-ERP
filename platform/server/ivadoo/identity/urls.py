from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    MeView,
    RecoveryCodesRegenerateView,
    SessionListView,
    SessionRevokeOthersView,
    SessionRevokeView,
    TotpConfirmView,
    TotpSetupView,
    TwoFactorDisableView,
    TwoFactorStatusView,
)


app_name = "identity"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("sessions/", SessionListView.as_view(), name="sessions"),
    path(
        "sessions/revoke-others/",
        SessionRevokeOthersView.as_view(),
        name="session-revoke-others",
    ),
    path(
        "sessions/<uuid:session_id>/revoke/",
        SessionRevokeView.as_view(),
        name="session-revoke",
    ),
    path("2fa/", TwoFactorStatusView.as_view(), name="two-factor-status"),
    path("2fa/totp/setup/", TotpSetupView.as_view(), name="two-factor-setup"),
    path(
        "2fa/totp/confirm/",
        TotpConfirmView.as_view(),
        name="two-factor-confirm",
    ),
    path(
        "2fa/disable/",
        TwoFactorDisableView.as_view(),
        name="two-factor-disable",
    ),
    path(
        "2fa/recovery-codes/regenerate/",
        RecoveryCodesRegenerateView.as_view(),
        name="two-factor-recovery-regenerate",
    ),
]
