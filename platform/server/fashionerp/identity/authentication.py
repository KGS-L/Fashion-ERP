from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiSession
from .services import digest_token, touch_api_session


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

        try:
            session = ApiSession.objects.select_related("user").get(
                token_digest=digest_token(raw_token)
            )
        except ApiSession.DoesNotExist as exc:
            raise AuthenticationFailed("Invalid authentication credentials.") from exc

        if session.is_revoked or session.is_expired() or not session.user.is_active:
            raise AuthenticationFailed("Invalid authentication credentials.")

        touch_api_session(session)
        return session.user, session

    def authenticate_header(self, request) -> str:
        return "Bearer"
