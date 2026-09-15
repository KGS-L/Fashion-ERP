from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


_ERROR_CODES = {
    status.HTTP_400_BAD_REQUEST: "validation_error",
    status.HTTP_401_UNAUTHORIZED: "authentication_required",
    status.HTTP_403_FORBIDDEN: "permission_denied",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
}


def ivadoo_exception_handler(
    exc: Exception,
    context: dict[str, Any],
) -> Response | None:
    response = exception_handler(exc, context)

    if response is None:
        return None

    request = context.get("request")
    request_id = request.headers.get("X-Request-ID") if request is not None else None

    code = getattr(exc, "ivadoo_code", None) or _ERROR_CODES.get(response.status_code, "api_error")

    if isinstance(response.data, dict) and "detail" in response.data:
        message = str(response.data["detail"])
        details: Any = {}
    else:
        message = "The request could not be processed."
        details = response.data

    response.data = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }

    return response
