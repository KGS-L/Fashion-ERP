from django.urls import path

from .views import LoginView, LogoutView, MeView, SessionListView, SessionRevokeView


app_name = "identity"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("sessions/", SessionListView.as_view(), name="sessions"),
    path(
        "sessions/<uuid:session_id>/revoke/",
        SessionRevokeView.as_view(),
        name="session-revoke",
    ),
]
