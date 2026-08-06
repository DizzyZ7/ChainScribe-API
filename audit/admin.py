from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "action",
        "entity_type",
        "entity_id",
        "actor",
        "outcome",
        "request_id",
    )
    list_filter = ("outcome", "entity_type", "action", "timestamp")
    search_fields = ("entity_id", "=request_id", "actor__username")
    readonly_fields = (
        "id",
        "timestamp",
        "request_id",
        "actor",
        "action",
        "entity_type",
        "entity_id",
        "outcome",
        "metadata",
    )
    ordering = ("-timestamp",)
    list_select_related = ("actor",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
