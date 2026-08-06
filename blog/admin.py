from django.contrib import admin

from audit.admin_mixins import AuditedAdminMixin

from .models import Article, Category, Comment


@admin.register(Category)
class CategoryAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "updated_at")
    list_filter = ("is_active", "created_at", "updated_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("name",)


@admin.register(Article)
class ArticleAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("title", "author", "category", "status", "created_at", "updated_at")
    list_filter = ("status", "category", "created_at", "updated_at")
    search_fields = ("title", "author__username")
    autocomplete_fields = ("author", "category")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)
    list_select_related = ("author", "category")


@admin.register(Comment)
class CommentAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "article", "author", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("body", "author__username", "article__title")
    autocomplete_fields = ("article", "author")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)
    list_select_related = ("article", "author")
