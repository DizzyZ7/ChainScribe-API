import logging
from typing import Any

from django.core.exceptions import SuspiciousOperation
from ninja.errors import HttpError, ValidationError
from ninja_extra.exceptions import APIException

logger = logging.getLogger("chainscribe.error")


def error_payload(
    request,
    detail: str,
    code: str,
    fields: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "detail": str(detail),
        "code": code,
        "request_id": str(getattr(request, "request_id", "")),
    }
    if fields:
        payload["fields"] = fields
    return payload


def _safe_validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "location": list(error.get("loc", ())),
            "message": error.get("msg", "Invalid value"),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors
    ]


def register_exception_handlers(api) -> None:
    @api.exception_handler(ValidationError)
    def validation_error_handler(request, exc):
        return api.create_response(
            request,
            error_payload(
                request,
                "Request validation failed.",
                "validation_error",
                _safe_validation_errors(exc),
            ),
            status=422,
        )

    @api.exception_handler(HttpError)
    def http_error_handler(request, exc):
        code_by_status = {
            400: "bad_request",
            401: "authentication_required",
            403: "permission_denied",
            404: "not_found",
            409: "conflict",
            422: "validation_error",
            429: "rate_limit_exceeded",
        }
        return api.create_response(
            request,
            error_payload(
                request,
                str(exc.message),
                code_by_status.get(exc.status_code, "request_error"),
            ),
            status=exc.status_code,
        )

    @api.exception_handler(APIException)
    def api_exception_handler(request, exc):
        status_code = getattr(exc, "status_code", 400)
        detail = getattr(exc, "detail", "Request failed.")
        if isinstance(detail, (dict, list)):
            fields = detail
            detail = "Request failed."
        else:
            fields = None
        return api.create_response(
            request,
            error_payload(request, str(detail), "jwt_error", fields),
            status=status_code,
        )

    @api.exception_handler(SuspiciousOperation)
    def suspicious_operation_handler(request, exc):
        logger.warning(
            "request.suspicious",
            extra={"request_id": str(getattr(request, "request_id", "")), "outcome": "denied"},
        )
        return api.create_response(
            request,
            error_payload(request, "Invalid request.", "bad_request"),
            status=400,
        )

    @api.exception_handler(Exception)
    def unhandled_exception_handler(request, exc):
        logger.exception(
            "request.unhandled_exception",
            extra={
                "request_id": str(getattr(request, "request_id", "")),
                "method": request.method,
                "route": request.path,
                "status_code": 500,
                "outcome": "failure",
            },
        )
        return api.create_response(
            request,
            error_payload(request, "Internal server error.", "internal_error"),
            status=500,
        )
