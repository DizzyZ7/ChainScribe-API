import json
import logging
import uuid
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from core.checks import production_security_checks
from core.logging import JsonFormatter, redact_text
from tests.helpers import ApiTestMixin


class HealthAndErrorContractTests(ApiTestMixin, TestCase):
    def test_liveness_does_not_query_database(self):
        with self.assertNumQueries(0):
            response = self.client.get("/api/v1/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_readiness_queries_database(self):
        response = self.client.get("/api/v1/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "chainscribe-api")

    def test_readiness_returns_safe_503_when_database_fails(self):
        broken_connection = MagicMock()
        broken_connection.cursor.side_effect = RuntimeError("database internals")
        with (
            patch("core.api.connections", {"default": broken_connection}),
            self.assertLogs("chainscribe.health", level="ERROR"),
        ):
            response = self.client.get("/api/v1/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "database_unavailable")
        self.assertNotIn("database internals", response.content.decode())

    def test_request_id_is_echoed_when_valid(self):
        request_id = str(uuid.uuid4())

        response = self.client.get("/api/v1/health/live", HTTP_X_REQUEST_ID=request_id)

        self.assertEqual(response["X-Request-ID"], request_id)

    def test_invalid_request_id_is_replaced(self):
        response = self.client.get("/api/v1/health/live", HTTP_X_REQUEST_ID="not-a-uuid")

        self.assertNotEqual(response["X-Request-ID"], "not-a-uuid")
        uuid.UUID(response["X-Request-ID"])

    def test_unknown_api_route_returns_json_404(self):
        response = self.client.get("/api/v1/does-not-exist")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "not_found")
        self.assertIn("request_id", response.json())

    def test_validation_error_does_not_echo_password_input(self):
        secret = "Secret-That-Must-Not-Be-Echoed!"
        response = self.post_json(
            "/api/v1/auth/register",
            {"username": "bad user", "password": secret, "unexpected": "field"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertNotIn(secret, response.content.decode())

    def test_unhandled_error_is_logged_and_response_is_generic(self):
        with patch("blog.api.filtered_articles", side_effect=RuntimeError("internal detail")):
            with self.assertLogs("chainscribe.error", level="ERROR"):
                response = self.client.get("/api/v1/articles")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["code"], "internal_error")
        self.assertNotIn("internal detail", response.content.decode())


class RateLimitAndHeaderTests(ApiTestMixin, TestCase):
    @override_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMITS={"auth": (100, 60), "write": (1, 60)},
    )
    def test_write_rate_limit_uses_shared_cache_contract(self):
        cache.clear()
        user = self.create_user("writer")
        headers, _ = self.opaque_header(user)

        first = self.post_json(
            "/api/v1/articles",
            {"title": "First", "content": "First body"},
            **headers,
        )
        second = self.post_json(
            "/api/v1/articles",
            {"title": "Second", "content": "Second body"},
            **headers,
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 429)

    def test_query_string_token_is_not_accepted(self):
        user = self.create_user("query-token")
        _, raw_token = self.opaque_header(user)

        response = self.client.get(f"/api/v1/auth/me?token={raw_token}")

        self.assertEqual(response.status_code, 401)

    def test_unknown_authorization_scheme_is_rejected(self):
        response = self.client.get(
            "/api/v1/auth/me",
            HTTP_AUTHORIZATION="Basic abc123",
        )

        self.assertEqual(response.status_code, 401)


class JsonLoggingTests(TestCase):
    def test_redactor_removes_opaque_and_jwt_tokens(self):
        opaque = "A" * 256
        jwt = "eyJheader.payload.signature"
        password = "multi word password"
        malformed_bearer = "short-token-that-must-still-be-private"

        redacted = redact_text(
            f"Authorization: Bearer {malformed_bearer}, token={opaque}, "
            f"jwt={jwt}, password={password}"
        )

        self.assertNotIn(opaque, redacted)
        self.assertNotIn(jwt, redacted)
        self.assertNotIn(password, redacted)
        self.assertNotIn(malformed_bearer, redacted)

    def test_formatter_emits_structured_json(self):
        record = logging.LogRecord(
            name="chainscribe.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="test.event",
            args=(),
            exc_info=None,
        )
        record.request_id = "request-1"
        record.status_code = 200

        payload = json.loads(JsonFormatter().format(record))

        self.assertEqual(payload["event"], "test.event")
        self.assertEqual(payload["request_id"], "request-1")
        self.assertEqual(payload["status_code"], 200)


class SecurityCheckTests(TestCase):
    @override_settings(ALLOWED_HOSTS=["*"])
    def test_wildcard_allowed_hosts_is_an_error(self):
        issues = production_security_checks(None)

        self.assertIn("chainscribe.E001", {issue.id for issue in issues})

    @override_settings(CORS_ALLOW_ALL_ORIGINS=True)
    def test_wildcard_cors_is_an_error(self):
        issues = production_security_checks(None)

        self.assertIn("chainscribe.E002", {issue.id for issue in issues})
