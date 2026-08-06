import hashlib
import logging
import secrets

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.models import AuditEvent
from audit.services import record_audit

from .exceptions import DuplicateUsernameError, InvalidCredentialsError
from .models import ApiToken, User
from .validators import normalize_username

logger = logging.getLogger("chainscribe.accounts")


def digest_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("ascii")).hexdigest()


def issue_api_token(*, user: User) -> tuple[ApiToken, str]:
    for _ in range(3):
        raw_token = secrets.token_urlsafe(192)
        if len(raw_token) != 256:
            raise RuntimeError("Opaque token generator returned an unexpected length")
        try:
            with transaction.atomic():
                token = ApiToken.objects.create(
                    user=user,
                    digest=digest_token(raw_token),
                    expires_at=timezone.now() + settings.API_TOKEN_TTL,
                )
            return token, raw_token
        except IntegrityError:
            continue
    raise RuntimeError("Could not generate a unique API token")


@transaction.atomic
def register_user(*, request, username: str, password: str) -> tuple[User, ApiToken, str]:
    normalized = normalize_username(username)
    if User.objects.filter(username__iexact=normalized).exists():
        raise DuplicateUsernameError
    candidate = User(username=normalized)
    validate_password(password, user=candidate)
    candidate.set_password(password)
    candidate.full_clean()
    try:
        candidate.save()
    except IntegrityError as exc:
        raise DuplicateUsernameError from exc
    token, raw_token = issue_api_token(user=candidate)
    record_audit(
        request=request,
        actor=candidate,
        action="user.created",
        entity_type="user",
        entity_id=candidate.pk,
    )
    logger.info(
        "auth.registered",
        extra={
            "request_id": str(request.request_id),
            "user_id": str(candidate.pk),
            "entity_type": "user",
            "entity_id": str(candidate.pk),
            "action": "create",
            "outcome": "success",
        },
    )
    return candidate, token, raw_token


def login_user(*, request, username: str, password: str) -> tuple[User, ApiToken, str]:
    normalized = normalize_username(username)
    user = authenticate(request=request, username=normalized, password=password)
    if user is None or not user.is_active:
        record_audit(
            request=request,
            action="auth.login",
            entity_type="user",
            outcome=AuditEvent.Outcome.DENIED,
        )
        logger.warning(
            "auth.login_denied",
            extra={"request_id": str(request.request_id), "action": "login", "outcome": "denied"},
        )
        raise InvalidCredentialsError
    with transaction.atomic():
        token, raw_token = issue_api_token(user=user)
        User.objects.filter(pk=user.pk).update(last_login=timezone.now())
        record_audit(
            request=request,
            actor=user,
            action="auth.login",
            entity_type="user",
            entity_id=user.pk,
        )
    logger.info(
        "auth.login",
        extra={
            "request_id": str(request.request_id),
            "user_id": str(user.pk),
            "action": "login",
            "outcome": "success",
        },
    )
    return user, token, raw_token


@transaction.atomic
def revoke_api_token(*, request, token: ApiToken) -> None:
    locked = ApiToken.objects.select_for_update().get(pk=token.pk)
    if locked.revoked_at is None:
        locked.revoked_at = timezone.now()
        locked.save(update_fields=("revoked_at",))
    record_audit(
        request=request,
        actor=locked.user,
        action="auth.logout",
        entity_type="api_token",
        entity_id=locked.pk,
    )
    logger.info(
        "auth.logout",
        extra={
            "request_id": str(request.request_id),
            "user_id": str(locked.user_id),
            "entity_type": "api_token",
            "entity_id": str(locked.pk),
            "action": "logout",
            "outcome": "success",
        },
    )
