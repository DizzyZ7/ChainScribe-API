import uuid
from unittest.mock import patch

from django.contrib import admin
from django.test import RequestFactory, TestCase

from accounts.models import ApiToken, User
from accounts.services import issue_api_token
from audit.models import AuditEvent
from blog.models import Article, Category, Comment
from tests.helpers import ApiTestMixin


class AdminConfigurationTests(ApiTestMixin, TestCase):
    def admin_request(self):
        request = RequestFactory().post("/admin/")
        request.user = self.create_user(
            f"admin-{uuid.uuid4().hex[:8]}", is_staff=True, is_superuser=True
        )
        request.request_id = uuid.uuid4()
        return request

    def test_required_models_are_registered(self):
        for model in (User, ApiToken, Category, Article, Comment, AuditEvent):
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)

    def test_audit_admin_is_fully_read_only(self):
        user = self.create_user("admin-user", is_staff=True, is_superuser=True)
        request = RequestFactory().get("/admin/audit/auditevent/")
        request.user = user
        model_admin = admin.site._registry[AuditEvent]

        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))

    def test_token_admin_never_exposes_raw_token_field(self):
        model_admin = admin.site._registry[ApiToken]

        self.assertNotIn("digest", model_admin.fields)
        self.assertNotIn("token", model_admin.fields)

    def test_category_admin_create_update_delete_are_audited(self):
        request = self.admin_request()
        model_admin = admin.site._registry[Category]
        category = Category(name="Admin category", slug="admin-category")

        model_admin.save_model(request, category, form=None, change=False)
        category.name = "Updated category"
        model_admin.save_model(request, category, form=None, change=True)
        category_id = category.pk
        model_admin.delete_model(request, category)

        self.assertTrue(
            AuditEvent.objects.filter(action="category.created", entity_id=category_id).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(action="category.updated", entity_id=category_id).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(action="category.deleted", entity_id=category_id).exists()
        )

    def test_category_admin_bulk_delete_is_audited(self):
        request = self.admin_request()
        model_admin = admin.site._registry[Category]
        categories = [
            Category.objects.create(name="First", slug="first"),
            Category.objects.create(name="Second", slug="second"),
        ]

        model_admin.delete_queryset(
            request,
            Category.objects.filter(pk__in=[category.pk for category in categories]),
        )

        self.assertEqual(
            AuditEvent.objects.filter(action="category.deleted").count(),
            2,
        )

    def test_token_admin_action_revokes_and_audits(self):
        request = self.admin_request()
        token_owner = self.create_user("admin-token-owner")
        token, _ = issue_api_token(user=token_owner)
        model_admin = admin.site._registry[ApiToken]

        with patch.object(model_admin, "message_user") as message_user:
            model_admin.revoke_selected_tokens(
                request,
                ApiToken.objects.filter(pk=token.pk),
            )

        token.refresh_from_db()
        self.assertIsNotNone(token.revoked_at)
        self.assertEqual(model_admin.fingerprint(token), f"{token.digest[:12]}...")
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request, token))
        self.assertTrue(
            AuditEvent.objects.filter(action="api_token.revoked", entity_id=token.pk).exists()
        )
        message_user.assert_called_once()
