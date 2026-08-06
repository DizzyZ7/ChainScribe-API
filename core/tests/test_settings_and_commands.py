import importlib.util
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase

from core.management.commands.wait_for_db import Command

SETTINGS_DIR = Path(__file__).resolve().parents[2] / "config" / "settings"


def load_settings_module(filename: str):
    module_name = f"config.settings._test_{filename}_{uuid.uuid4().hex}"
    base_name = "config.settings.base"
    previous_base = sys.modules.pop(base_name, None)
    try:
        spec = importlib.util.spec_from_file_location(module_name, SETTINGS_DIR / f"{filename}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop(module_name, None)
        sys.modules.pop(base_name, None)
        if previous_base is not None:
            sys.modules[base_name] = previous_base


class SettingsTests(SimpleTestCase):
    def test_development_settings_follow_debug_environment(self):
        with patch.dict(os.environ, {"DJANGO_DEBUG": "true"}):
            module = load_settings_module("development")

        self.assertTrue(module.DEBUG)
        self.assertTrue(module.API_DOCS_ENABLED)

    def test_production_settings_require_secrets_and_services(self):
        required = {
            "DJANGO_SECRET_KEY": "",
            "JWT_SIGNING_KEY": "",
            "POSTGRES_PASSWORD": "",
            "REDIS_URL": "",
        }
        with patch.dict(os.environ, required):
            with self.assertRaises(ImproperlyConfigured):
                load_settings_module("production")

    def test_production_settings_reject_short_secrets(self):
        environment = {
            "DJANGO_SECRET_KEY": "short",
            "JWT_SIGNING_KEY": "short",
            "POSTGRES_PASSWORD": "database-secret",
            "REDIS_URL": "redis://redis:6379/0",
            "CORS_ALLOWED_ORIGINS": "https://example.com",
            "CSRF_TRUSTED_ORIGINS": "https://example.com",
        }
        with patch.dict(os.environ, environment):
            with self.assertRaises(ImproperlyConfigured):
                load_settings_module("production")

    def test_production_settings_enable_transport_security(self):
        environment = {
            "DJANGO_SECRET_KEY": "d" * 64,
            "JWT_SIGNING_KEY": "j" * 64,
            "POSTGRES_PASSWORD": "database-secret",
            "REDIS_URL": "redis://redis:6379/0",
            "CORS_ALLOWED_ORIGINS": "https://example.com",
            "CSRF_TRUSTED_ORIGINS": "https://example.com",
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "TRUST_PROXY_HEADERS": "true",
        }
        with patch.dict(os.environ, environment):
            module = load_settings_module("production")

        self.assertFalse(module.DEBUG)
        self.assertFalse(module.API_DOCS_ENABLED)
        self.assertTrue(module.SESSION_COOKIE_SECURE)
        self.assertTrue(module.CSRF_COOKIE_SECURE)
        self.assertEqual(module.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertEqual(module.NINJA_JWT["SIGNING_KEY"], "j" * 64)


class WaitForDatabaseCommandTests(TestCase):
    def test_wait_for_db_succeeds_against_database(self):
        call_command("wait_for_db", verbosity=0)

    def test_wait_for_db_retries_operational_error(self):
        connection = MagicMock()
        ready_context = MagicMock()
        ready_cursor = ready_context.__enter__.return_value
        connection.cursor.side_effect = [OperationalError("not ready"), ready_context]

        with (
            patch("core.management.commands.wait_for_db.connections", {"default": connection}),
            patch("core.management.commands.wait_for_db.time.monotonic", side_effect=[0, 0.1, 0.2]),
            patch("core.management.commands.wait_for_db.time.sleep") as sleep,
        ):
            Command().handle()

        connection.close.assert_called_once()
        sleep.assert_called_once_with(0.25)
        ready_cursor.execute.assert_called_once_with("SELECT 1")
        ready_cursor.fetchone.assert_called_once()

    def test_wait_for_db_times_out_safely(self):
        with (
            patch.dict(os.environ, {"DB_WAIT_TIMEOUT": "0"}),
            patch("core.management.commands.wait_for_db.time.monotonic", side_effect=[0, 0]),
            self.assertRaises(CommandError),
        ):
            Command().handle()
