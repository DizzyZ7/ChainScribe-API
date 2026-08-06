from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from core.errors import error_payload

from .api import api


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
]


def handler404(request, exception):
    if request.path.startswith("/api/"):
        return JsonResponse(error_payload(request, "Resource not found.", "not_found"), status=404)
    return JsonResponse({"detail": "Not found."}, status=404)


def handler500(request):
    if request.path.startswith("/api/"):
        return JsonResponse(
            error_payload(request, "Internal server error.", "internal_error"), status=500
        )
    return JsonResponse({"detail": "Internal server error."}, status=500)


admin.site.site_header = "ChainScribe administration"
admin.site.site_title = "ChainScribe Admin"
admin.site.index_title = "Publishing operations"
