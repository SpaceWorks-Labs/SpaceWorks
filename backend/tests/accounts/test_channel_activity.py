"""Channel analytics recording: web session-days, per-channel call counts, the flush and the purge."""

from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import channel_usage
from apps.accounts.models_activity import ChannelUsageDay, DeviceActivityDay, WebSessionActivityDay
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.accounts.web_sessions import create_session
from tests.return_helpers import make_member, make_space
from tests.test_native_push import device_client, push_member

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fresh_buffer(monkeypatch):
    # No Redis in the test cache: counts sit in the per-process buffer until flushed.
    monkeypatch.setattr("apps.apiclients.telemetry.get_redis_client", lambda: None)
    # Per-user caches (active spaces, session-hour dedupe) outlive a rolled-back test and user pks repeat.
    cache.clear()
    channel_usage._local.clear()
    yield
    channel_usage._local.clear()


def web_client(user, session=False):
    token = SpaceWorksRefreshToken.for_user(user)
    token["surface"] = "member"
    if session:  # a real server-side session: an unknown `sid` fails validate_session
        create_session(user, token)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def test_web_session_day_is_recorded_once_per_session_space_and_day_without_identifiers():
    space = make_space("chan-web")
    user = make_member("chan-web-user", space)
    client = web_client(user)
    for _ in range(3):
        assert client.get("/api/v1/auth/me").status_code == 200
    rows = WebSessionActivityDay.objects.filter(user=user)
    assert rows.count() == 1 and rows.get().makerspace_id == space.pk
    assert len(rows.get().session_hash) == 32
    # A second session of the same person is a second row; the marker is hashed, never stored.
    web_client(user, session=True).get("/api/v1/auth/me")
    assert rows.count() == 2
    assert not any("session:" in str(value) for value in rows.values_list("session_hash", flat=True))
    fields = {field.name for field in WebSessionActivityDay._meta.get_fields()}
    assert fields.isdisjoint({"ip", "ip_address", "user_agent", "token", "jti", "sid"})


def test_calls_are_counted_by_channel_and_area_then_flushed_to_the_database():
    space = make_space("chan-calls")
    user = make_member("chan-calls-user", space)
    web_client(user).get("/api/v1/auth/me")
    web_client(user).get("/api/v1/auth/me")
    assert not ChannelUsageDay.objects.exists()  # cached first, written by the flush
    assert channel_usage.flush_usage() == 2
    row = ChannelUsageDay.objects.get(channel="web", makerspace=space)
    assert row.count == 2 and row.area == "accounts" and row.day == timezone.now().date()
    assert channel_usage.flush_usage() == 0  # drained: a second flush adds nothing
    assert ChannelUsageDay.objects.get(pk=row.pk).count == 2


def test_phone_calls_count_as_the_platform_channel_and_keep_device_activity():
    space = make_space("chan-phone")
    user = push_member("chan-phone-user", space)
    client, grant = device_client(user, space, platform="android")
    assert client.get("/api/v1/auth/me").status_code == 200
    channel_usage.flush_usage()
    assert ChannelUsageDay.objects.filter(channel="android").exists()
    assert DeviceActivityDay.objects.filter(grant=grant, platform="android").exists()
    assert not ChannelUsageDay.objects.filter(channel__in=("web", "ios")).exists()


def test_area_is_the_serving_app_and_unknown_routes_fall_back_to_other():
    class View:
        __module__ = "apps.events.views_public"
    request = SimpleNamespace(resolver_match=SimpleNamespace(func=SimpleNamespace(cls=View)))
    assert channel_usage.area_for(request) == "events"
    assert channel_usage.area_for(SimpleNamespace(resolver_match=None)) == "other"


class FakePipe:
    def __init__(self, redis):
        self.redis, self.steps = redis, []

    def hincrby(self, *args):
        self.steps.append(("hincrby", args))

    def expire(self, *args):
        self.steps.append(("expire", args))

    def exists(self, *args):
        self.steps.append(("exists", args))

    def execute(self):
        return [getattr(self.redis, name)(*args) for name, args in self.steps]


class FakeRedis:
    def __init__(self):
        self.hashes = {}

    def pipeline(self):
        return FakePipe(self)

    def hincrby(self, key, field, amount):
        bucket = self.hashes.setdefault(key, {})
        bucket[field] = bucket.get(field, 0) + amount

    def expire(self, *_args):
        return True

    def exists(self, key):
        return int(key in self.hashes)

    def rename(self, source, target):
        self.hashes[target] = self.hashes.pop(source)

    def hgetall(self, key):
        return {field: str(value) for field, value in self.hashes.get(key, {}).items()}

    def delete(self, key):
        self.hashes.pop(key, None)


def test_redis_buckets_are_flushed_by_the_beat_task_and_an_interrupted_flush_is_recovered(monkeypatch):
    from apps.accounts.tasks_channel_usage import flush_channel_usage_task
    space = make_space("chan-redis")
    fake = FakeRedis()
    monkeypatch.setattr("apps.apiclients.telemetry.get_redis_client", lambda: fake)
    request = SimpleNamespace(resolver_match=SimpleNamespace(func=SimpleNamespace(cls=type("V", (), {"__module__": "apps.bookings.views"}))))
    for _ in range(4):
        channel_usage.record_call("ios", request, space.pk)
    channel_usage.record_call("api_client", request, None)
    channel_usage.record_call("nonsense", request, None)  # an unknown channel is never counted
    assert flush_channel_usage_task() == 5
    assert ChannelUsageDay.objects.get(channel="ios", area="bookings", makerspace=space).count == 4
    assert ChannelUsageDay.objects.get(channel="api_client", makerspace=None).count == 1
    assert not fake.hashes
    # A flush interrupted after the rename leaves ":flushing"; the next run finishes it exactly once.
    key = channel_usage._bucket_key(timezone.now())
    fake.hashes[key + ":flushing"] = {f"web|bookings|{space.pk}": 3}
    assert flush_channel_usage_task() == 3
    assert ChannelUsageDay.objects.get(channel="web", area="bookings", makerspace=space).count == 3


def test_account_purge_removes_web_session_activity_including_unselected_rows():
    from apps.accounts.account_purge import _global_rows
    space = make_space("chan-purge")
    user, other = make_member("chan-purge-user", space), make_member("chan-purge-other", space)
    today = timezone.localdate()
    for who, selected in ((user, space), (user, None), (other, space)):
        WebSessionActivityDay.objects.create(user=who, session_hash="a" * 32, makerspace=selected, local_day=today)
    _global_rows(user)
    assert not WebSessionActivityDay.objects.filter(user=user).exists()
    assert WebSessionActivityDay.objects.filter(user=other).count() == 1


def test_web_session_activity_is_classified_exported_and_snapshotted():
    from apps.data_export.classification_m1f1 import OMITTED_MODELS
    from apps.data_export.subject_runtime import RUNTIME_FIELDS
    from apps.data_export.subject_selectors import SUBJECT_PATHS
    from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES
    for label in ("accounts.WebSessionActivityDay", "accounts.ChannelUsageDay"):
        assert label in OMITTED_MODELS and label in FIRST_PARTY_FIELD_NAMES
    assert "accounts.WebSessionActivityDay" in RUNTIME_FIELDS and "accounts.WebSessionActivityDay" in SUBJECT_PATHS
    assert "session_hash" not in RUNTIME_FIELDS["accounts.WebSessionActivityDay"]


def _flow_request(url_name, channel, method="POST", space=None):
    view = type("V", (), {"__module__": "apps.hardware_requests.views"})
    return SimpleNamespace(method=method, sw_channel=channel, sw_channel_space=space,
                           resolver_match=SimpleNamespace(url_name=url_name, func=SimpleNamespace(cls=view)))


def test_successful_key_flow_posts_count_per_channel_and_failures_and_reads_do_not():
    from django.http import HttpResponse
    from apps.accounts.channel_middleware import ChannelUsageMiddleware
    space = make_space("chan-flow")
    cases = [("request-submit", "web", "POST", 201), ("request-submit", "ios", "POST", 201),
             ("request-submit", "web", "POST", 400), ("request-submit", "web", "GET", 200),
             ("member-booking-checkout", "android", "POST", 200), ("not-a-flow", "web", "POST", 200)]
    for name, channel, method, status in cases:
        ChannelUsageMiddleware(lambda _r, status=status: HttpResponse(status=status))(_flow_request(name, channel, method, space.pk))
    channel_usage.flush_usage()
    flows = {(r.channel, r.area): r.count for r in ChannelUsageDay.objects.filter(area__startswith="flow:")}
    assert flows == {("web", "flow:request_submitted"): 1, ("ios", "flow:request_submitted"): 1,
                     ("android", "flow:booking_made"): 1}
