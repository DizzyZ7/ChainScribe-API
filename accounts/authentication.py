import logging
import re
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from django.utils import timezone
from ninja.errors import HttpError
from ninja.security import HttpBearer
from ninja.security.base import AuthBase
from ninja_jwt.authentication import JWTAuth

from .models import ApiToken
from .services import digest_token

logger = logging.getLogger("chainscribe.authentication")
OPAQUE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{256}$")


def _authenticate_opaque(request, raw_token: str):
    if not OPAQUE_TOKEN_PATTERN.fullmatch(raw_token):
        logger.warning(
            "auth.opaque_malformed",
            extra={"request_id": str(request.request_id), "outcome": "denied"},
        )
        return None
    now = timezone.now()
    token = (
        ApiToken.objects.select_related("user")
        .filter(
            digest=digest_token(raw_token),
            revoked_at__isnull=True,
            expires_at__gt=now,
            user__is_active=True,
        )
        .first()
    )
    if token is None:
        logger.warning(
            "auth.opaque_invalid",
            extra={"request_id": str(request.request_id), "outcome": "denied"},
        )
        return None
    touch_before = now - settings.API_TOKEN_TOUCH_INTERVAL
    ApiToken.objects.filter(pk=token.pk).filter(
        Q(last_used_at__isnull=True) | Q(last_used_at__lt=touch_before)
    ).update(last_used_at=now)
    request.user = token.user
    request.api_token = token
    return token.user


class OpaqueTokenAuth(HttpBearer):
    openapi_scheme = "token"

    def authenticate(self, request, token):
        return _authenticate_opaque(request, token)


@dataclass(frozen=True)
class PublicPrincipal:
    name: str = "public"


PUBLIC_PRINCIPAL = PublicPrincipal()


class DualTokenAuth(AuthBase):
    openapi_type = "http"
    openapi_scheme = "bearer"
    openapi_description = "Use 'Token <opaque-token>' or 'Bearer <jwt-access-token>'."

    def __init__(self, optional: bool = False):
        self.optional = optional
        self.jwt_auth = JWTAuth()
        super().__init__()

    def __call__(self, request):
        authorization = request.headers.get("Authorization")
        if not authorization:
            if self.optional:
                request.user = AnonymousUser()
                return PUBLIC_PRINCIPAL
            return None
        parts = authorization.split()
        if len(parts) != 2:
            raise HttpError(401, "Invalid Authorization header.")
        scheme, token = parts
        if scheme.lower() == "token":
            user = _authenticate_opaque(request, token)
        elif scheme.lower() == "bearer":
            user = self.jwt_auth.jwt_authenticate(request, token)
        else:
            raise HttpError(401, "Unsupported Authorization scheme.")
        if user is None:
            raise HttpError(401, "Invalid or expired credentials.")
        return user


opaque_auth = OpaqueTokenAuth()
dual_auth = DualTokenAuth()
optional_dual_auth = DualTokenAuth(optional=True)
