from .services import record_audit


class AuditedAdminMixin:
    def save_model(self, request, obj, form, change):
        action = "updated" if change else "created"
        super().save_model(request, obj, form, change)
        record_audit(
            request=request,
            actor=request.user,
            action=f"{obj._meta.model_name}.{action}",
            entity_type=obj._meta.model_name,
            entity_id=obj.pk,
            metadata={"source": "django_admin"},
        )

    def delete_model(self, request, obj):
        model_name = obj._meta.model_name
        entity_id = obj.pk
        super().delete_model(request, obj)
        record_audit(
            request=request,
            actor=request.user,
            action=f"{model_name}.deleted",
            entity_type=model_name,
            entity_id=entity_id,
            metadata={"source": "django_admin"},
        )

    def delete_queryset(self, request, queryset):
        model_name = queryset.model._meta.model_name
        entity_ids = list(queryset.values_list("pk", flat=True))
        super().delete_queryset(request, queryset)
        for entity_id in entity_ids:
            record_audit(
                request=request,
                actor=request.user,
                action=f"{model_name}.deleted",
                entity_type=model_name,
                entity_id=entity_id,
                metadata={"source": "django_admin_bulk"},
            )
