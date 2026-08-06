from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse, JsonResponse
from ninja import Router
from ninja_jwt.schema import (
    TokenBlacklistInputSchema,
    TokenObtainPairInputSchema,
    TokenObtainPairOutputSchema,
    TokenRefreshInputSchema,
    TokenRefreshOutputSchema,
    TokenVerifyInputSchema,
)

from audit.services import record_audit
from core.errors import error_payload
from core.schemas import ErrorSchema

from .authentication import dual_auth, opaque_auth
from .exceptions import DuplicateUsernameError, InvalidCredentialsError
from .schemas import LoginInput, OpaqueTokenOutput, RegisterInput, UserOutput
from .services import login_user, register_user, revoke_api_token

router = Router(tags=["Authentication"])
jwt_router = Router(tags=["Authentication: JWT"])


def _user_payload(user) -> dict:
    return {"id": user.pk, "username": user.username, "date_joined": user.date_joined}


def _token_response(user, token, raw_token: str, status: int) -> JsonResponse:
    response = JsonResponse(
        {
            "token": raw_token,
            "token_type": "Token",
            "expires_at": token.expires_at,
            "user": _user_payload(user),
        },
        status=status,
    )
    response["Cache-Control"] = "no-store"
    return response


@router.post(
    "/register",
    auth=None,
    response={201: OpaqueTokenOutput, 409: ErrorSchema, 422: ErrorSchema},
)
def register(request, payload: RegisterInput):
    try:
        user, token, raw_token = register_user(
            request=request,
            username=payload.username,
            password=payload.password.get_secret_value(),
        )
    except DuplicateUsernameError:
        return JsonResponse(
            error_payload(request, "Username is already registered.", "username_conflict"),
            status=409,
        )
    except DjangoValidationError as exc:
        fields = exc.message_dict if hasattr(exc, "message_dict") else {"password": exc.messages}
        return JsonResponse(
            error_payload(
                request,
                "Registration validation failed.",
                "validation_error",
                fields,
            ),
            status=422,
        )
    return _token_response(user, token, raw_token, 201)


@router.post(
    "/login",
    auth=None,
    response={200: OpaqueTokenOutput, 401: ErrorSchema},
)
def login(request, payload: LoginInput):
    try:
        user, token, raw_token = login_user(
            request=request,
            username=payload.username,
            password=payload.password.get_secret_value(),
        )
    except InvalidCredentialsError:
        return JsonResponse(
            error_payload(request, "Invalid username or password.", "invalid_credentials"),
            status=401,
        )
    return _token_response(user, token, raw_token, 200)


@router.post("/logout", auth=opaque_auth, response={204: None, 401: ErrorSchema})
def logout(request):
    revoke_api_token(request=request, token=request.api_token)
    return HttpResponse(status=204)


@router.get("/me", auth=dual_auth, response={200: UserOutput, 401: ErrorSchema})
def me(request):
    return _user_payload(request.user)


@jwt_router.post("/pair", auth=None, response=TokenObtainPairOutputSchema)
def jwt_pair(request, user_token: TokenObtainPairInputSchema):
    user_token.check_user_authentication_rule()
    response = user_token.to_response_schema()
    record_audit(
        request=request,
        actor=user_token._user,
        action="auth.jwt_login",
        entity_type="user",
        entity_id=user_token._user.pk,
    )
    return response


@jwt_router.post("/refresh", auth=None, response=TokenRefreshOutputSchema)
def jwt_refresh(request, refresh_token: TokenRefreshInputSchema):
    return refresh_token.to_response_schema()


@jwt_router.post("/verify", auth=None, response=dict)
def jwt_verify(request, token: TokenVerifyInputSchema):
    return token.to_response_schema()


@jwt_router.post("/blacklist", auth=None, response=dict)
def jwt_blacklist(request, refresh: TokenBlacklistInputSchema):
    result = refresh.to_response_schema()
    record_audit(
        request=request,
        action="auth.jwt_logout",
        entity_type="jwt_refresh",
    )
    return result
