"""Exercise actual confirmation attempts against the supported database cache."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.cache import caches
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import override_settings
from rest_framework.exceptions import Throttled, ValidationError

from apps.notifications import browser_firebase_challenge as proof
from apps.notifications.models_browser_firebase import BrowserFirebaseRegistration


@pytest.mark.django_db(transaction=True)
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache",
                                      "LOCATION": "test_firebase_attempt_cache"}})
def test_five_confirm_attempts_are_atomic_on_database_cache(monkeypatch, request):
    call_command("createcachetable", "test_firebase_attempt_cache", verbosity=0)
    # A transactional test leaves its DDL behind; an extra table in a reused test database breaks
    # the tenant-dump "unowned table universe" guard for every later test.
    request.addfinalizer(lambda: connection.cursor().execute("DROP TABLE IF EXISTS test_firebase_attempt_cache"))
    caches["default"].clear()
    actor, space = SimpleNamespace(pk=1), SimpleNamespace(pk=2)
    challenge = str(uuid4())
    monkeypatch.setattr(proof, "send_challenge", lambda *args: None)
    proof.begin(actor=actor, space=space, project="test-project", fid="test-fid",
                challenge=challenge, push_settings=None)
    barrier = Barrier(12)

    def attempt(_):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                proof.confirm(actor=actor, space=space, project="test-project", fid="test-fid",
                              challenge=challenge, nonce="definitely-wrong")
            except Throttled:
                return "throttled"
            except ValidationError:
                return "invalid"
            return "unexpected-success"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=12) as pool:
        outcomes = list(pool.map(attempt, range(12)))
    assert outcomes.count("invalid") == 5
    assert outcomes.count("throttled") == 7
    assert len(outcomes) == 12
    assert not BrowserFirebaseRegistration.objects.exists()