from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils import timezone

from audit.admin_mixins import AuditedAdminMixin
from audit.services import record_audit

from .models import ApiToken, User


@admin.register(User)
class UserAdmin(AuditedAdminMixin, DjangoUserAdmin):
    list_display = ("username", "is_active", "is_staff", "date_joined", "last_login")
    list_filter = ("is_active", "is_staff", "is_superuser", "date_joined")
    search_fields = ("username",)
    ordering = ("username",)
    readonly_fields = ("id", "date_joined", "last_login")
    fieldsets = (
        (None, {"fields": ("id", "username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )


@admin.register(ApiToken)
class ApiTokenAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "user", "fingerprint", "created_at", "expires_at", "revoked_at")
    list_filter = ("created_at", "expires_at", "revoked_at")
    search_fields = ("id", "user__username")
    readonly_fields = (
        "id",
        "user",
        "fingerprint",
        "created_at",
        "expires_at",
        "revoked_at",
        "last_used_at",
    )
    fields = readonly_fields
    ordering = ("-created_at",)
    list_select_related = ("user",)
    actions = ("revoke_selected_tokens",)

    @admin.display(description="Digest fingerprint")
    def fingerprint(self, obj):
        return f"{obj.digest[:12]}..."

    @admin.action(description="Revoke selected API tokens")
    def revoke_selected_tokens(self, request, queryset):
        now = timezone.now()
        tokens = list(queryset.filter(revoked_at__isnull=True))
        ApiToken.objects.filter(pk__in=[token.pk for token in tokens]).update(revoked_at=now)
        for token in tokens:
            record_audit(
                request=request,
                actor=request.user,
                action="api_token.revoked",
                entity_type="api_token",
                entity_id=token.pk,
                metadata={"source": "django_admin"},
            )
        self.message_user(request, f"Revoked {len(tokens)} token(s).", messages.SUCCESS)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
