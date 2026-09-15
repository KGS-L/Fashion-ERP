from django.utils import translation
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiSession
from .services import digest_token, touch_api_session


def resolve_api_session(raw_token: str, *, using: str = "default") -> ApiSession:
    try:
        session = (
            ApiSession.objects.using(using)
            .select_related("user")
            .get(token_digest=digest_token(raw_token))
        )
    except ApiSession.DoesNotExist as exc:
        raise AuthenticationFailed("Invalid authentication credentials.") from exc

    if session.is_revoked or session.is_expired() or not session.user.is_active:
        raise AuthenticationFailed("Invalid authentication credentials.")

    return session


class OpaqueBearerAuthentication(BaseAuthentication):
    keyword = b"bearer"

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth:
            return None

        if auth[0].lower() != self.keyword:
            return None

        if len(auth) != 2:
            raise AuthenticationFailed("Invalid authentication credentials.")

        try:
            raw_token = auth[1].decode("utf-8")
        except UnicodeError as exc:
            raise AuthenticationFailed("Invalid authentication credentials.") from exc

        session = resolve_api_session(raw_token)

        # The module gate runs only after a valid server-side session has bound
        # the request to the local organization. It is therefore a capability
        # check, not a tenant selector.
        from ivadoo.extensibility.services import assert_api_module_enabled

        assert_api_module_enabled(session.user.organization, request.path)
        touch_api_session(session)
        translation.activate(session.user.language_code)
        return session.user, session

    def authenticate_header(self, request) -> str:
        return "Bearer"
