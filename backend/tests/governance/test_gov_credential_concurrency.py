"""Credential operations serialize on real connections without stale bearers winning."""
import pytest as _pytest_stale

# STALE (R3 test phase): owner decisions #63/#66 retired the separate staff account and the
# Space Manager's create/set-password/deactivate/resend-account paths (d55545d7, d7f674a7).
# Replacement coverage: tests/admin_api/test_staff_roles_api.py and the /control/ disable tests.
_pytest_stale.skip("staff accounts retired by #63/#66 (d55545d7)", allow_module_level=True)


from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from django.db import close_old_connections, connection, transaction
from rest_framework.exceptions import APIException

from apps.accounts.credential_locks import lock_credentials
from apps.accounts.models import PasswordResetEnvelope
from apps.accounts.services_password_reset import confirm_password_reset, request_password_reset
from apps.accounts.services_password_reset_drain import (
    claim_pending_envelopes, finalize_delivery, prepare_delivery,
)
from apps.accounts.staff_account_lifecycle import deactivate, set_password
from apps.accounts.staff_account_services import create
from apps.accounts.staff_invitation_acceptance import accept
from tests.account_split.p3_helpers import PASSWORD, context

pytestmark = pytest.mark.django_db(transaction=True)
ORIGIN = "http://localhost:5000"
RECOVERED = "Recovered governance credential 936!"
ADMIN_PASSWORD = "Administrator issued governance 438!"


@pytest.fixture
def recovery(settings, monkeypatch):
    settings.PUBLIC_APP_BASE_URL = ORIGIN
    monkeypatch.setattr("apps.integrations.email.platform_email_configured", lambda: True)
    monkeypatch.setattr("apps.accounts.services_password_reset_drain.platform_email_configured", lambda: True)
    ctx = context(settings)
    # The shared lifecycle fixture has no mail address; recovery needs a deliverable
    # account before either contender reaches the credential locks.
    ctx.worker.email = "governance-worker@example.test"
    ctx.worker.save(update_fields=("email",))
    return ctx


def issue(user, space):
    envelope = request_password_reset(user.email, context="staff", makerspace=space.slug, origin=ORIGIN)
    assert envelope is not None
    claim = claim_pending_envelopes(owner="governance-race")[0]
    attempt = prepare_delivery(claim)
    assert attempt is not None and not isinstance(attempt, str)
    assert finalize_delivery(claim, delivered=True)
    return attempt.code


def race(user, first, second):
    """Hold the first operation's real credential locks while starting its rival."""
    locked, started, release = Event(), Event(), Event()

    def run(operation, owns_first_lock):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '12s'")
            if owns_first_lock:
                with transaction.atomic():
                    lock_credentials(user)
                    locked.set()
                    assert release.wait(timeout=15)
                    return operation()
            started.set()
            return operation()
        except APIException:
            return "refused"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(run, first, True)
        assert locked.wait(timeout=15)
        b = pool.submit(run, second, False)
        assert started.wait(timeout=15)
        release.set()
        return a.result(timeout=35), b.result(timeout=35)


def reset(user, space, code):
    return confirm_password_reset(user.email, code, RECOVERED, context="staff",
                                  makerspace=space.slug, origin=ORIGIN)


@pytest.mark.parametrize("first", ["reset", "redeem"])
def test_email_reset_vs_invitation_redemption(recovery, first):
    ctx = recovery
    user, invitation = create(ctx.manager, ctx.space.pk, display_name="Recovery race",
        email="governance-race@example.test", roles=["handover"])
    row, raw = invitation
    code = issue(user, ctx.space)
    operations = {
        "reset": lambda: reset(user, ctx.space, code),
        "redeem": lambda: accept(None, token=raw, makerspace_slug=ctx.space.slug, password=PASSWORD),
    }
    outcomes = race(user, operations[first], operations["redeem" if first == "reset" else "reset"])
    user.refresh_from_db()
    row.refresh_from_db()
    assert outcomes[0] != "refused"
    if first == "reset":
        assert user.check_password(RECOVERED) and user.credential_generation == 1
        assert outcomes[1] == "refused" and row.revoked_at is not None and row.accepted_at is None
    else:
        assert user.check_password(PASSWORD) and user.credential_generation == 0
        assert outcomes[1] == "refused" and row.accepted_at is not None
    with pytest.raises(APIException):
        reset(user, ctx.space, code)


@pytest.mark.parametrize("first", ["reset", "admin"])
def test_email_reset_vs_admin_password_issue(recovery, first):
    ctx = recovery
    code = issue(ctx.worker, ctx.space)
    operations = {
        "reset": lambda: reset(ctx.worker, ctx.space, code),
        "admin": lambda: set_password(ctx.manager, ctx.space.pk, ctx.worker.pk, password=ADMIN_PASSWORD),
    }
    a, b = race(ctx.worker, operations[first], operations["admin" if first == "reset" else "reset"])
    ctx.worker.refresh_from_db()
    assert a != "refused"
    assert ctx.worker.check_password(ADMIN_PASSWORD) and ctx.worker.must_change_password
    assert ctx.worker.credential_generation == (2 if first == "reset" else 1)
    assert (b != "refused") if first == "reset" else (b == "refused")
    with pytest.raises(APIException):
        reset(ctx.worker, ctx.space, code)


@pytest.mark.parametrize("first", ["worker", "deactivate"])
def test_worker_issuance_vs_deactivation(recovery, first):
    ctx = recovery
    envelope = request_password_reset(ctx.worker.email, context="staff",
        makerspace=ctx.space.slug, origin=ORIGIN)
    assert envelope is not None
    claim = claim_pending_envelopes(owner="governance-worker-race")[0]
    operations = {
        "worker": lambda: prepare_delivery(claim),
        "deactivate": lambda: deactivate(ctx.manager, ctx.space.pk, ctx.worker.pk),
    }
    a, b = race(ctx.worker, operations[first], operations["deactivate" if first == "worker" else "worker"])
    ctx.worker.refresh_from_db()
    envelope.refresh_from_db()
    assert not ctx.worker.is_active and ctx.worker.credential_generation == 1
    assert not envelope.digest_is_live and envelope.status == "discarded"
    assert not finalize_delivery(claim, delivered=True)
    if first == "worker":
        assert a is not None and not isinstance(a, str)
    else:
        assert b is None or isinstance(b, str)
    assert PasswordResetEnvelope.objects.filter(user=ctx.worker).count() == 1
