from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from audit.models import AuditEvent
from audit.services import record_audit
from tests.helpers import ApiTestMixin


class AuditEventTests(ApiTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user("auditor")
        self.request = RequestFactory().get("/")
        self.request.request_id = "c4dd1c49-d9cf-4f17-b8c1-1a954fd0dcae"

    def test_audit_event_redacts_sensitive_metadata(self):
        event = record_audit(
            request=self.request,
            actor=self.user,
            action="test.created",
            entity_type="test",
            entity_id="1",
            metadata={
                "token": "secret-token",
                "content": "publication text",
                "safe": "value",
                "unexpected_secret": "A" * 256,
            },
        )

        self.assertEqual(event.metadata["token"], "[REDACTED]")
        self.assertEqual(event.metadata["content"], "[REDACTED]")
        self.assertEqual(event.metadata["safe"], "value")
        self.assertNotIn("A" * 256, event.metadata["unexpected_secret"])

    def test_saved_audit_event_cannot_be_changed_or_deleted(self):
        event = record_audit(
            request=self.request,
            actor=self.user,
            action="test.created",
            entity_type="test",
        )
        event.action = "tampered"

        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()
        with self.assertRaises(ValidationError):
            AuditEvent.objects.filter(pk=event.pk).update(action="tampered")
        with self.assertRaises(ValidationError):
            AuditEvent.objects.filter(pk=event.pk).delete()

    def test_oversized_metadata_is_replaced(self):
        event = record_audit(
            request=self.request,
            actor=self.user,
            action="test.created",
            entity_type="test",
            metadata={"safe": "x" * 5000},
        )

        self.assertEqual(event.metadata, {"truncated": True})
