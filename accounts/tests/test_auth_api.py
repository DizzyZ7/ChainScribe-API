from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.models import ApiToken
from audit.models import AuditEvent
from tests.helpers import ApiTestMixin, TEST_PASSWORD


class OpaqueAuthenticationApiTests(ApiTestMixin, TestCase):
    def test_register_returns_exact_token_and_hashes_storage(self):
        response = self.post_json(
            "/api/v1/auth/register",
            {"username": "New.Writer", "password": TEST_PASSWORD},
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(len(body["token"]), 256)
        self.assertEqual(body["token_type"], "Token")
        self.assertEqual(body["user"]["username"], "new.writer")
        self.assertEqual(response["Cache-Control"], "no-store")
        token = ApiToken.objects.get(user__username="new.writer")
        self.assertNotEqual(token.digest, body["token"])
        self.assertNotIn(body["token"], repr(token.__dict__))
        self.assertTrue(
            AuditEvent.objects.filter(action="user.created", entity_id=str(token.user_id)).exists()
        )

    def test_register_rejects_duplicate_normalized_username(self):
        self.create_user("alice")

        response = self.post_json(
            "/api/v1/auth/register",
            {"username": "ALICE", "password": TEST_PASSWORD},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "username_conflict")

    def test_register_rejects_weak_password_without_echoing_it(self):
        weak_password = "password"
        response = self.post_json(
            "/api/v1/auth/register",
            {"username": "weak-user", "password": weak_password},
        )

        self.assertEqual(response.status_code, 422)
        self.assertNotIn(weak_password, response.content.decode())

    def test_register_rejects_unicode_and_extra_authority_fields(self):
        response = self.post_json(
            "/api/v1/auth/register",
            {
                "username": "admіn",
                "password": TEST_PASSWORD,
                "is_superuser": True,
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertFalse(ApiToken.objects.exists())

    def test_login_success_issues_a_new_token(self):
        user = self.create_user("login-user")

        response = self.post_json(
            "/api/v1/auth/login",
            {"username": "LOGIN-USER", "password": TEST_PASSWORD},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["token"]), 256)
        self.assertEqual(response.json()["user"]["id"], str(user.pk))
        self.assertTrue(AuditEvent.objects.filter(action="auth.login", actor=user).exists())

    def test_login_failure_is_generic_and_audited(self):
        self.create_user("login-user")

        response = self.post_json(
            "/api/v1/auth/login",
            {"username": "login-user", "password": "definitely-wrong"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid username or password.")
        self.assertTrue(
            AuditEvent.objects.filter(action="auth.login", outcome="denied").exists()
        )

    def test_logout_revokes_current_token(self):
        user = self.create_user("logout-user")
        headers, raw_token = self.opaque_header(user)

        response = self.post_json("/api/v1/auth/logout", {}, **headers)

        self.assertEqual(response.status_code, 204)
        token = ApiToken.objects.get(digest__isnull=False)
        self.assertIsNotNone(token.revoked_at)
        me_response = self.client.get(
            "/api/v1/auth/me", HTTP_AUTHORIZATION=f"Token {raw_token}"
        )
        self.assertEqual(me_response.status_code, 401)

    def test_logout_rejects_missing_or_jwt_credentials(self):
        user = self.create_user("logout-user")
        jwt_headers, _ = self.jwt_header(user)

        missing = self.post_json("/api/v1/auth/logout", {})
        jwt_response = self.post_json("/api/v1/auth/logout", {}, **jwt_headers)

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(jwt_response.status_code, 401)

    def test_me_accepts_opaque_token(self):
        user = self.create_user("opaque-user")
        headers, _ = self.opaque_header(user)

        response = self.client.get("/api/v1/auth/me", **headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], str(user.pk))

    def test_me_accepts_jwt_and_rejects_missing_credentials(self):
        user = self.create_user("jwt-user")
        headers, _ = self.jwt_header(user)

        jwt_response = self.client.get("/api/v1/auth/me", **headers)
        missing_response = self.client.get("/api/v1/auth/me")

        self.assertEqual(jwt_response.status_code, 200)
        self.assertEqual(jwt_response.json()["username"], "jwt-user")
        self.assertEqual(missing_response.status_code, 401)

    @override_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMITS={"auth": (1, 60), "write": (100, 60)},
    )
    def test_auth_rate_limit_returns_429(self):
        cache.clear()
        first = self.post_json(
            "/api/v1/auth/register",
            {"username": "rate-one", "password": TEST_PASSWORD},
        )
        second = self.post_json(
            "/api/v1/auth/register",
            {"username": "rate-two", "password": TEST_PASSWORD},
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["code"], "rate_limit_exceeded")
        self.assertIn("Retry-After", second)

    def test_auth_logs_never_contain_password_or_returned_token(self):
        password = "Unique-Logging-Password-2026!"
        with self.assertLogs("chainscribe", level="INFO") as captured:
            response = self.post_json(
                "/api/v1/auth/register",
                {"username": "log-user", "password": password},
            )

        output = "\n".join(captured.output)
        self.assertEqual(response.status_code, 201)
        self.assertNotIn(password, output)
        self.assertNotIn(response.json()["token"], output)


class JwtAuthenticationApiTests(ApiTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user("jwt-login")

    def test_pair_returns_access_and_refresh_tokens(self):
        response = self.post_json(
            "/api/v1/auth/jwt/pair",
            {"username": self.user.username, "password": TEST_PASSWORD},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertTrue(
            AuditEvent.objects.filter(action="auth.jwt_login", actor=self.user).exists()
        )

    def test_pair_rejects_wrong_password_generically(self):
        response = self.post_json(
            "/api/v1/auth/jwt/pair",
            {"username": self.user.username, "password": "wrong-password"},
        )

        self.assertIn(response.status_code, {400, 401})
        self.assertNotIn("wrong-password", response.content.decode())

    def test_refresh_rotates_and_blacklists_previous_token(self):
        pair = self.post_json(
            "/api/v1/auth/jwt/pair",
            {"username": self.user.username, "password": TEST_PASSWORD},
        ).json()

        response = self.post_json(
            "/api/v1/auth/jwt/refresh",
            {"refresh": pair["refresh"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.assertNotEqual(response.json()["refresh"], pair["refresh"])
        reused = self.post_json(
            "/api/v1/auth/jwt/refresh",
            {"refresh": pair["refresh"]},
        )
        self.assertGreaterEqual(reused.status_code, 400)

    def test_refresh_rejects_invalid_token(self):
        response = self.post_json(
            "/api/v1/auth/jwt/refresh",
            {"refresh": "not-a-jwt"},
        )

        self.assertGreaterEqual(response.status_code, 400)

    def test_verify_accepts_valid_access_token(self):
        headers, access = self.jwt_header(self.user)
        self.assertTrue(headers["HTTP_AUTHORIZATION"].startswith("Bearer "))

        response = self.post_json("/api/v1/auth/jwt/verify", {"token": access})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {})

    def test_verify_rejects_invalid_token(self):
        response = self.post_json("/api/v1/auth/jwt/verify", {"token": "invalid"})

        self.assertGreaterEqual(response.status_code, 400)

    def test_blacklist_revokes_refresh_token(self):
        pair = self.post_json(
            "/api/v1/auth/jwt/pair",
            {"username": self.user.username, "password": TEST_PASSWORD},
        ).json()

        response = self.post_json(
            "/api/v1/auth/jwt/blacklist",
            {"refresh": pair["refresh"]},
        )
        reused = self.post_json(
            "/api/v1/auth/jwt/refresh",
            {"refresh": pair["refresh"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(reused.status_code, 400)
        self.assertTrue(AuditEvent.objects.filter(action="auth.jwt_logout").exists())

    def test_blacklist_rejects_malformed_refresh(self):
        response = self.post_json(
            "/api/v1/auth/jwt/blacklist",
            {"refresh": "malformed"},
        )

        self.assertGreaterEqual(response.status_code, 400)
