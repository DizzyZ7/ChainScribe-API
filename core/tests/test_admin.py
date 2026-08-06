from django.contrib import admin
from django.test import RequestFactory, TestCase

from accounts.models import ApiToken, User
from audit.models import AuditEvent
from blog.models import Article, Category, Comment
from tests.helpers import ApiTestMixin


class AdminConfigurationTests(ApiTestMixin, TestCase):
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
