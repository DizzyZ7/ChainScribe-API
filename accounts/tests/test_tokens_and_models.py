from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from accounts.models import ApiToken, User
from accounts.services import digest_token, issue_api_token
from tests.helpers import ApiTestMixin


class ApiTokenTests(ApiTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user("token-user")

    def test_issue_token_has_fixed_length_and_only_digest_is_stored(self):
        token, raw_token = issue_api_token(user=self.user)

        self.assertEqual(len(raw_token), 256)
        self.assertRegex(raw_token, r"^[A-Za-z0-9_-]{256}$")
        self.assertEqual(token.digest, digest_token(raw_token))
        self.assertFalse(hasattr(token, "raw_token"))

    def test_tokens_are_unique(self):
        _, first = issue_api_token(user=self.user)
        _, second = issue_api_token(user=self.user)

        self.assertNotEqual(first, second)
        self.assertEqual(ApiToken.objects.filter(user=self.user).count(), 2)

    def test_expired_token_is_rejected(self):
        token, raw_token = issue_api_token(user=self.user)
        token.expires_at = timezone.now() - timedelta(seconds=1)
        token.save(update_fields=("expires_at",))

        response = self.client.get(
            "/api/v1/auth/me",
            HTTP_AUTHORIZATION=f"Token {raw_token}",
        )

        self.assertEqual(response.status_code, 401)

    def test_malformed_token_is_rejected(self):
        response = self.client.get(
            "/api/v1/auth/me",
            HTTP_AUTHORIZATION="Token too-short",
        )

        self.assertEqual(response.status_code, 401)

    def test_last_used_is_touched_but_not_on_every_request(self):
        token, raw_token = issue_api_token(user=self.user)
        old_touch = timezone.now() - timedelta(hours=1)
        ApiToken.objects.filter(pk=token.pk).update(last_used_at=old_touch)

        first = self.client.get("/api/v1/auth/me", HTTP_AUTHORIZATION=f"Token {raw_token}")
        token.refresh_from_db()
        first_touch = token.last_used_at
        second = self.client.get("/api/v1/auth/me", HTTP_AUTHORIZATION=f"Token {raw_token}")
        token.refresh_from_db()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertGreater(first_touch, old_touch)
        self.assertEqual(token.last_used_at, first_touch)

    def test_token_string_and_usable_state_do_not_disclose_digest(self):
        token, _ = issue_api_token(user=self.user)

        self.assertTrue(token.is_usable)
        self.assertNotIn(token.digest, str(token))
        token.revoked_at = timezone.now()
        self.assertFalse(token.is_usable)


class UserModelTests(TestCase):
    def test_username_is_normalized_before_storage(self):
        user = User.objects.create_user(username="  MiXeD.Name  ", password="x")

        self.assertEqual(user.username, "mixed.name")

    def test_case_variant_cannot_be_created(self):
        User.objects.create_user(username="alice", password="x")

        with self.assertRaises(IntegrityError):
            User.objects.create_user(username="ALICE", password="x")
