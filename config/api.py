from django.conf import settings
from ninja_extra import NinjaExtraAPI

from accounts.api import jwt_router, router as accounts_router
from blog.api import router as blog_router
from core.api import router as core_router
from core.errors import register_exception_handlers


api = NinjaExtraAPI(
    title="ChainScribe API",
    version="1.0.0",
    description="Security-focused publishing backend with opaque-token and JWT authentication.",
    docs_url="/docs" if settings.API_DOCS_ENABLED else None,
    urls_namespace="chainscribe-api",
)
register_exception_handlers(api)
api.add_router("", core_router)
api.add_router("/auth", accounts_router)
api.add_router("/auth/jwt", jwt_router)
api.add_router("", blog_router)
