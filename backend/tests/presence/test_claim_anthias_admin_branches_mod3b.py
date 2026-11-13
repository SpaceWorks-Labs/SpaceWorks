"""MOD-3B: the remaining branches of presence claim ending, Anthias network blocking, the Anthias
Celery task and the superuser-only presence admin."""
import importlib
import uuid
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address, ip_network
from types import SimpleNamespace

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.contrib import admin
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import MemberClaimCode
from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership
from apps.presence import anthias_networks, services_claim, tasks_anthias
from apps.presence.models import PresenceSession
from apps.presence.models_anthias import AnthiasPlayer
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


def _member_with_session(slug, *, ends_in=60):
    space = make_space(slug)
    user = make_member(f"{slug}-user", space, membership_role="custom")
    membership = MakerspaceMembership.objects.get(makerspace=space, user=user)
    now = timezone.now()
    session = PresenceSession.objects.create(
        member=user, makerspace=space, membership=membership, started_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=ends_in))
    return space, user, membership, session


def _claim(membership, **kwargs):
    return MemberClaimCode.objects.create(
        membership=membership, code_digest=uuid.uuid4().hex + uuid.uuid4().hex,
        expires_at=timezone.now() + timedelta(hours=1), **kwargs)


def _tied_session(space, user, membership, claim):
    now = timezone.now()
    return PresenceSession.objects.create(
        member=user, makerspace=space, membership=membership, started_at=now - timedelta(minutes=2),
        expires_at=now + timedelta(minutes=30), created_via_claim_session=claim)


# --- services_claim -------------------------------------------------------------------
def test_membership_revocation_ends_only_that_members_live_sessions_with_audit(monkeypatch):
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(services_claim.timezone, "now", lambda: now)
    space, user, membership, session = _member_with_session("m3b-rev")
    _s2, _u2, _m2, foreign = _member_with_session("m3b-rev-other")
    actor = make_member("m3b-rev-actor", space)
    foreign_before = PresenceSession.objects.values().get(pk=foreign.pk)
    services_claim.end_sessions_for_membership(actor, membership)
    session.refresh_from_db()
    foreign.refresh_from_db()
    assert (session.ended_at, session.ended_by_id, session.end_reason) == (now, actor.pk, "membership_revoked")
    assert session.ended_by == actor
    assert session.end_reason == "membership_revoked"
    assert foreign.ended_at is None
    assert PresenceSession.objects.values().get(pk=foreign.pk) == foreign_before
    assert AuditLog.objects.filter(makerspace=foreign.makerspace, action__startswith="presence.ended_").count() == 0
    assert list(AuditLog.objects.filter(action__startswith="presence.ended_").values_list(
        "makerspace_id", "target_type", "target_id", "actor_id", "action", "meta")) == [
        (space.pk, "presence.presencesession", str(session.pk), actor.pk, "presence.ended_membership_revoked", {})]
    assert AuditLog.objects.filter(action="presence.ended_membership_revoked", target_id=str(session.pk),
                                   makerspace=space).count() == 1


def test_claim_revocation_ends_exactly_the_sessions_carrying_the_claim_fk():
    space, user, membership, untied = _member_with_session("m3b-claim")
    claim = _claim(membership)
    tied = _tied_session(space, user, membership, claim)
    now = timezone.now()
    services_claim.end_sessions_for_claim(claim, ended_at=now, actor=None)
    tied.refresh_from_db()
    untied.refresh_from_db()
    assert tied.ended_at == now and tied.end_reason == "claim_revoked" and tied.ended_by is None
    assert untied.ended_at is None
    row = AuditLog.objects.get(action="presence.ended_claim_revoked", target_id=str(tied.pk))
    assert row.meta == {"claim_session_id": str(claim.session_id)}


@pytest.mark.parametrize("field", ["session_id", "membership_id"])
def test_claim_with_inconsistent_provenance_is_refused_without_ending_anything(field):
    space, user, membership, session = _member_with_session("m3b-inconsistent")
    claim = _claim(membership)
    tied = _tied_session(space, user, membership, claim)
    stale = SimpleNamespace(pk=claim.pk, session_id=claim.session_id, membership_id=claim.membership_id)
    setattr(stale, field, uuid.uuid4() if field == "session_id" else -1)
    with pytest.raises(RuntimeError, match="provenance is inconsistent"):
        services_claim.end_sessions_for_claim(stale, ended_at=timezone.now(), actor=None)
    tied.refresh_from_db()
    assert tied.ended_at is None


@pytest.mark.parametrize("state,ends", [("revoked", True), ("expired", True), ("live", False), ("unconsumed", False)])
def test_expire_claim_presence_only_ends_for_a_revoked_or_expired_claim(state, ends, monkeypatch):
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(services_claim.timezone, "now", lambda: now)
    space, user, membership, untied = _member_with_session(f"m3b-exp-{state}")
    claim = _claim(membership, revoked_at=now if state == "revoked" else None,
                   absolute_expires_at=(None if state == "unconsumed" else
                                        now - timedelta(seconds=1) if state == "expired" else now + timedelta(hours=1)))
    tied = _tied_session(space, user, membership, claim)
    before = PresenceSession.objects.values().get(pk=tied.pk)
    untied_before = PresenceSession.objects.values().get(pk=untied.pk)
    claim_before = MemberClaimCode.objects.values().get(pk=claim.pk)
    services_claim.expire_claim_presence(claim.session_id)
    tied.refresh_from_db()
    expected_end = (now, None, "claim_revoked") if ends else (None, None, "")
    assert (tied.ended_at, tied.ended_by_id, tied.end_reason) == expected_end
    assert PresenceSession.objects.values().get(pk=untied.pk) == untied_before
    assert MemberClaimCode.objects.values().get(pk=claim.pk) == claim_before
    ending_audits = AuditLog.objects.filter(action__startswith="presence.ended_")
    if ends:
        assert list(ending_audits.values_list(
            "makerspace_id", "target_type", "target_id", "actor_id", "action", "meta")) == [
            (space.pk, "presence.presencesession", str(tied.pk), None, "presence.ended_claim_revoked",
             {"claim_session_id": str(claim.session_id)})]
        assert ending_audits.count() == 1
    else:
        assert PresenceSession.objects.values().get(pk=tied.pk) == before
        assert ending_audits.count() == 0


def test_expire_claim_presence_for_an_unknown_session_changes_nothing():
    _space, _user, _m, session = _member_with_session("m3b-exp-unknown")
    services_claim.expire_claim_presence(uuid.uuid4())
    session.refresh_from_db()
    assert session.ended_at is None


def test_claim_scope_validation_refuses_another_member_or_makerspace():
    space, user, membership, _ = _member_with_session("m3b-scope")
    claim = _claim(membership)
    services_claim._validate_claim_scope(claim, user, space)
    other_space, other_user, _m, _s = _member_with_session("m3b-scope-other")
    for who, where in ((other_user, space), (user, other_space)):
        with pytest.raises(PermissionDenied) as refused:
            services_claim._validate_claim_scope(claim, who, where)
        assert refused.value.status_code == 403
        assert refused.value.get_codes() == "permission_denied"


# --- anthias_networks -----------------------------------------------------------------
@pytest.fixture(autouse=True)
def _fresh_cache():
    anthias_networks.reset_cache()
    yield
    anthias_networks.reset_cache()


def test_configured_networks_skip_garbage_and_accept_host_bits(settings):
    settings.OUTBOUND_BLOCKED_NETWORKS = ["10.1.2.3/16", " 192.0.2.0/24 ", "not-a-cidr", ""]
    assert anthias_networks._configured() == [ip_network("10.1.0.0/16"), ip_network("192.0.2.0/24")]
    settings.OUTBOUND_BLOCKED_NETWORKS = None
    assert anthias_networks._configured() == []


def test_connected_networks_are_empty_outside_a_container(tmp_path):
    route = tmp_path / "route"
    route.write_text("Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\n")
    assert anthias_networks._connected(str(route), marker=str(tmp_path / "missing")) == []


def test_connected_networks_read_directly_attached_routes_only(tmp_path):
    marker = tmp_path / ".dockerenv"
    marker.write_text("")
    route = tmp_path / "route"
    header = "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT"
    lines = [
        header,
        "eth0\t00000000\t010011AC\t0003\t0\t0\t0\t00000000\t0\t0\t0",   # default route: skipped
        "eth0\t000011AC\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0",   # 172.17.0.0/16 directly connected
        "eth1\t0000A8C0\t00000000\t0001\t0\t0\t0\t00FFFFFF\t0\t0\t0",   # 192.168.0.0/24
        "short line",
        "eth2\tZZZZ\t00000000\t0001\t0\t0\t0\t00FFFFFF\t0\t0\t0",      # bad hex
    ]
    route.write_text("\n".join(lines))
    assert anthias_networks._connected(str(route), str(marker)) == [
        ip_network("172.17.0.0/16"), ip_network("192.168.0.0/24")]


def test_connected_networks_tolerate_an_unreadable_route_table(tmp_path):
    marker = tmp_path / ".dockerenv"
    marker.write_text("")
    assert anthias_networks._connected(str(tmp_path / "no-such-route"), str(marker)) == []


def test_own_addresses_parse_scoped_ipv6_and_survive_resolver_failure(monkeypatch):
    infos = [(0, 0, 0, "", ("10.9.8.7", 0)), (0, 0, 0, "", ("fe80::1%eth0", 0, 0, 1)), (0, 0, 0, "", ("bogus", 0))]
    monkeypatch.setattr(anthias_networks.socket, "getaddrinfo", lambda *a, **k: infos)
    assert anthias_networks._own_addresses() == [ip_network("10.9.8.7/32"), ip_network("fe80::1/128")]

    def boom(*a, **k):
        raise OSError("no resolver")
    monkeypatch.setattr(anthias_networks.socket, "getaddrinfo", boom)
    assert anthias_networks._own_addresses() == []


def test_service_networks_are_cached_for_five_minutes_then_rebuilt(monkeypatch, settings):
    settings.OUTBOUND_BLOCKED_NETWORKS = ["10.77.0.0/16"]
    monkeypatch.setattr(anthias_networks, "_connected", lambda: [])
    monkeypatch.setattr(anthias_networks, "_own_addresses", lambda: [])
    clock = {"now": 1000.0}
    monkeypatch.setattr(anthias_networks, "time", SimpleNamespace(monotonic=lambda: clock["now"]))
    first = anthias_networks.service_networks()
    assert first == (ip_network("10.77.0.0/16"),)
    settings.OUTBOUND_BLOCKED_NETWORKS = ["10.88.0.0/16"]
    clock["now"] += anthias_networks.CACHE_SECONDS
    assert anthias_networks.service_networks() is first
    clock["now"] += 1
    rebuilt = anthias_networks.service_networks()
    assert rebuilt == (ip_network("10.88.0.0/16"),)
    assert ip_address("10.88.1.1") in rebuilt[0]


# --- tasks_anthias --------------------------------------------------------------------
class _Retry(Exception):
    pass


def _player(slug):
    return AnthiasPlayer.objects.create(makerspace=make_space(slug), name="Lobby", host_url="http://192.0.2.10")


def _run(monkeypatch, player_id, retries=0):
    calls = []

    def retry(countdown):
        calls.append(countdown)
        raise _Retry

    task = tasks_anthias.sync_anthias_player_task
    monkeypatch.setattr(task, "retry", retry)
    task.push_request(retries=retries)
    try:
        task.run(player_id)
    except _Retry:
        pass
    finally:
        task.pop_request()
    return calls


def test_a_missing_player_is_a_silent_no_op(monkeypatch):
    monkeypatch.setattr(tasks_anthias, "sync_player", lambda p: pytest.fail("must not sync"))
    assert _run(monkeypatch, 987654321) == []


@pytest.mark.parametrize("error,retries,countdown", [
    ("timeout", 0, 30), ("unreachable", 2, 120), ("dns_failed", 5, 900), ("http_error", 1, 60)])
def test_a_retryable_failure_is_retried_with_doubling_backoff_capped_at_fifteen_minutes(
        monkeypatch, error, retries, countdown):
    player = _player(f"m3b-task-{error}".replace("_", "-"))

    def failing(p):
        p.status, p.last_error = AnthiasPlayer.Status.ERROR, error
    monkeypatch.setattr(tasks_anthias, "sync_player", failing)
    assert _run(monkeypatch, player.pk, retries=retries) == [countdown]


def test_a_permanent_failure_is_not_retried(monkeypatch):
    player = _player("m3b-task-perm")

    def failing(p):
        p.status, p.last_error = AnthiasPlayer.Status.ERROR, "bad_credentials"
    monkeypatch.setattr(tasks_anthias, "sync_player", failing)
    assert _run(monkeypatch, player.pk) == []


def test_a_successful_sync_does_not_retry_even_with_a_stale_error(monkeypatch):
    player = _player("cx4-task-success")

    def successful(p):
        p.status, p.last_error = AnthiasPlayer.Status.OK, "timeout"

    monkeypatch.setattr(tasks_anthias, "sync_player", successful)
    assert _run(monkeypatch, player.pk) == []


def test_the_soft_time_limit_marks_the_player_timed_out_and_retries(monkeypatch):
    player = _player("m3b-task-soft")

    def slow(p):
        raise SoftTimeLimitExceeded()
    monkeypatch.setattr(tasks_anthias, "sync_player", slow)
    assert _run(monkeypatch, player.pk) == [30]
    player.refresh_from_db()
    assert player.status == AnthiasPlayer.Status.ERROR and player.last_error == "timeout"


# --- admin ----------------------------------------------------------------------------
def test_the_presence_admin_is_read_only_and_superuser_only():
    from django.contrib.auth.models import AnonymousUser

    from apps.accounts.models import User
    from apps.presence.admin import PresenceSessionAdmin
    model_admin = PresenceSessionAdmin(PresenceSession, admin.site)
    factory = RequestFactory()
    superuser = User.objects.create_superuser(username="m3b-admin-su", email="m3b-su@example.test", password="x-Pass-12345")
    plain = make_member("m3b-admin-plain", make_space("m3b-admin2"))

    def request(method, user):
        built = getattr(factory, method)("/")
        built.user = user
        return built

    assert model_admin.has_add_permission(request("get", superuser)) is False
    assert model_admin.has_change_permission(request("get", superuser)) is True
    assert model_admin.has_change_permission(request("head", superuser)) is True
    assert model_admin.has_change_permission(request("post", superuser)) is False
    assert model_admin.has_change_permission(request("get", plain)) is False
    assert model_admin.has_change_permission(request("get", AnonymousUser())) is False
    assert set(model_admin.readonly_fields) == {f.name for f in PresenceSession._meta.fields}


def test_a_tombstoned_presence_app_registers_no_admin_screen(monkeypatch):
    import apps.presence.admin as module
    monkeypatch.setattr("apps.separability.tombstones.app_is_tombstoned", lambda label: True)
    if PresenceSession in admin.site._registry:
        admin.site.unregister(PresenceSession)
    try:
        importlib.reload(module)
        assert PresenceSession not in admin.site._registry
    finally:
        monkeypatch.undo()
        if PresenceSession in admin.site._registry:
            admin.site.unregister(PresenceSession)
        importlib.reload(module)
        assert PresenceSession in admin.site._registry


def test_membership_revocation_skips_expired_ended_and_other_members_and_replay_is_inert(monkeypatch):
    space, user, membership, live = _member_with_session("cx4-claim-end")
    now = timezone.now()
    monkeypatch.setattr(services_claim.timezone, "now", lambda: now)
    expired = PresenceSession.objects.create(member=user, makerspace=space, membership=membership,
        started_at=now - timedelta(hours=1), expires_at=now)
    ended = PresenceSession.objects.create(member=user, makerspace=space, membership=membership,
        started_at=now - timedelta(minutes=5), expires_at=now + timedelta(hours=1),
        ended_at=now - timedelta(minutes=1), end_reason="user_ended")
    other = make_member("cx4-claim-bystander", space, membership_role="custom")
    other_membership = MakerspaceMembership.objects.get(user=other, makerspace=space)
    untouched = _tied_session(space, other, other_membership, _claim(other_membership))
    services_claim.end_sessions_for_membership(user, membership)
    services_claim.end_sessions_for_membership(user, membership)
    live.refresh_from_db()
    expired.refresh_from_db()
    ended.refresh_from_db()
    untouched.refresh_from_db()
    assert (live.ended_at, live.ended_by_id, live.end_reason) == (now, user.pk, "membership_revoked")
    assert expired.ended_at is None
    assert ended.ended_at == now - timedelta(minutes=1)
    assert ended.end_reason == "user_ended"
    assert untouched.ended_at is None
    assert list(AuditLog.objects.filter(action="presence.ended_membership_revoked", makerspace=space)
                .values_list("target_id", flat=True)) == [str(live.pk)]


def test_claim_expiry_at_the_exact_boundary_ends_once_with_the_original_actor_empty(monkeypatch):
    space, user, membership, untied = _member_with_session("cx4-claim-boundary")
    now = timezone.now()
    monkeypatch.setattr(services_claim.timezone, "now", lambda: now)
    claim = _claim(membership, absolute_expires_at=now)
    tied = _tied_session(space, user, membership, claim)
    services_claim.expire_claim_presence(claim.session_id)
    services_claim.expire_claim_presence(claim.session_id)
    tied.refresh_from_db()
    untied.refresh_from_db()
    assert (tied.ended_at, tied.ended_by_id, tied.end_reason) == (now, None, "claim_revoked")
    assert untied.ended_at is None
    assert AuditLog.objects.filter(action="presence.ended_claim_revoked", target_id=str(tied.pk)).count() == 1
