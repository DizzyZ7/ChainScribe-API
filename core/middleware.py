import hashlib
import logging
import time
import uuid

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse


logger = logging.getLogger("chainscribe.request")
AUTH_RATE_LIMIT_PATHS = {
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/jwt/pair",
}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _request_id(value: str | None) -> uuid.UUID:
    if value:
        try:
            parsed = uuid.UUID(value)
            if str(parsed) == value.lower():
                return parsed
        except (TypeError, ValueError, AttributeError):
            value = None
    return uuid.uuid4()


def _client_identity(request) -> str:
    remote_addr = request.META.get("REMOTE_ADDR", "unknown")
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            remote_addr = forwarded.split(",", 1)[0].strip()
    return hashlib.sha256(remote_addr.encode("utf-8")).hexdigest()


def _error_payload(request, detail: str, code: str) -> dict:
    return {
        "detail": detail,
        "code": code,
        "request_id": str(getattr(request, "request_id", "")),
    }


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = _request_id(request.headers.get("X-Request-ID"))
        started = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - started) * 1000, 2)
        response["X-Request-ID"] = str(request.request_id)
        if request.path.startswith("/api/v1/auth/") and response.status_code < 400:
            response["Cache-Control"] = "no-store"
        user = getattr(request, "user", None)
        logger.info(
            "request.completed",
            extra={
                "request_id": str(request.request_id),
                "method": request.method,
                "route": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_id": str(user.pk)
                if user is not None and getattr(user, "is_authenticated", False)
                else None,
                "outcome": "success" if response.status_code < 400 else "failure",
            },
        )
        return response


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        scope = self._scope(request)
        if scope and not self._allow(request, scope):
            logger.warning(
                "rate_limit.exceeded",
                extra={
                    "request_id": str(request.request_id),
                    "method": request.method,
                    "route": request.path,
                    "status_code": 429,
                    "outcome": "denied",
                },
            )
            response = JsonResponse(
                _error_payload(request, "Too many requests.", "rate_limit_exceeded"),
                status=429,
            )
            response["Retry-After"] = str(settings.RATE_LIMITS[scope][1])
            return response
        return self.get_response(request)

    @staticmethod
    def _scope(request) -> str | None:
        if not settings.RATE_LIMIT_ENABLED or not request.path.startswith("/api/v1/"):
            return None
        if request.path in AUTH_RATE_LIMIT_PATHS and request.method == "POST":
            return "auth"
        if request.method in WRITE_METHODS:
            return "write"
        return None

    @staticmethod
    def _allow(request, scope: str) -> bool:
        limit, window_seconds = settings.RATE_LIMITS[scope]
        window = int(time.time()) // window_seconds
        identity = _client_identity(request)
        raw_key = f"ratelimit:{scope}:{identity}:{window}"
        key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        if cache.add(key, 1, timeout=window_seconds + 1):
            return True
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=window_seconds + 1)
            count = 1
        return count <= limit
