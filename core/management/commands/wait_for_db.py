import os
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Wait for the default database to accept connections."

    def handle(self, *args, **options):
        deadline = time.monotonic() + int(os.getenv("DB_WAIT_TIMEOUT", "60"))
        delay = 0.25
        while time.monotonic() < deadline:
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                self.stdout.write(self.style.SUCCESS("Database is ready."))
                return
            except OperationalError:
                connections["default"].close()
                time.sleep(delay)
                delay = min(delay * 2, 5)
        raise CommandError("Database did not become ready before the timeout.")
