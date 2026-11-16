"""Payload v2 on real member/staff transports, with only HTTP and signing mocked."""

from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from apps.integrations.dispatch_channels import dispatch_channel
from apps.integrations.models import NotificationDeliveryLog
from apps.accounts.models import DeviceGrant
from apps.integrations.models import PushDevice
from apps.integrations.notification_delivery import send
from django.utils import timezone
from tests.account_split.p1_helpers import staff
from tests.accounts.account_factories import device_grant
from apps.notifications.member_push import deliver_row
from apps.notifications.models_push import MemberPushDelivery
from tests.notifications.test_support_m1b import push_case, wire_message  # noqa: F401

pytestmark = pytest.mark.django_db


def add_local_staff(case):
    user, _ = staff(case.space, "m1b-staff", "space_manager", access_status="active")
    # Staff grants must satisfy the native-staff context (password, MFA, attestation, fixed tenant).
    grant = device_grant(user, case.grant.registration, signing_identity=case.grant.signing_identity,
        attestation_subject_fingerprint="e" * 64)
    device = PushDevice(user=user, makerspace=case.space, device_grant=grant,
        provider=case.device.provider, environment="development", token_fingerprint="e" * 64)
    device.set_token("m1b-device-token")
    device.save()
    return user


def assert_provider_contract(case, index, expected_data, expected_body, title=None):
    from apps.integrations.push_payload import short_body, short_title
    alert, data = wire_message(case, index)
    assert alert == {"title": short_title(title or case.space.name), "body": short_body(expected_body)}
    assert data == expected_data
    assert all(isinstance(value, str) for value in data.values())
    call = case.calls[index]
    if case.device.provider == "apns":
        assert call["json"]["aps"]["thread-id"] == str(case.space.pk)
        assert "apns-collapse-id" not in call["headers"]
        assert call["headers"]["apns-topic"] == "org.spaceworks.app"
        assert call["headers"]["apns-push-type"] == "alert"
    else:
        message = call["json"]["message"]
        assert set(message) == {"token", "notification", "data", "android"}
        assert message["android"] == {"notification": {
            "channel_id": "sw_bookings", "tag": f"sw-{expected_data['event_id']}"}}
        assert message["token"] == "m1b-device-token"
        assert call["timeout"] == 10
        assert call["headers"]["Authorization"] == "Bearer oauth-test-token"


@pytest.mark.parametrize("push_case", ["fcm", "apns"], indirect=True)
def test_separate_staff_and_member_accounts_get_their_own_payload(push_case):
    case = push_case
    staff_user = add_local_staff(case)
    assert staff_user.pk != case.user.pk and case.user.account_kind == "member"
    key = uuid4()
    [log] = dispatch_channel(makerspace=case.space, channel="native_push",
        feature="bookings", event="confirmed", text_body=case.staff_text,
        payload={"event_key": str(key)}, sync=True)
    assert log.status == "sent"
    assert_provider_contract(case, 0, {"v": "3", "event_id": str(key),
        "makerspace_id": str(case.space.pk), "feature": "bookings", "event": "confirmed",
        "channel": "sw_bookings", "category": "sw.open"}, case.staff_text)
    parent = case.prepare()
    send(parent.pk)
    assert_provider_contract(case, 1, {"v": "3", "channel": "sw_bookings", "category": "sw.inbox",
        "event_id": str(uuid5(NAMESPACE_URL, case.envelope.dedup_key)),
        "makerspace_id": str(case.space.pk), "feature": "bookings", "event": "confirmed",
        "inbox_row_id": str(case.inbox.pk), "link": f"/m/{case.space.slug}/member"}, case.summary, title="Your booking")
    assert MemberPushDelivery.objects.get(envelope_delivery=parent).status == "sent"
    # The retained identifier is inert; an inbox write cannot send a second push.
    assert deliver_row(case.inbox.pk) is False
    assert len(case.calls) == 2


@pytest.mark.parametrize("push_case", ["fcm", "apns"], indirect=True)
@pytest.mark.parametrize("audience", ["member", "staff"])
@pytest.mark.parametrize("link,accepted", [
    ("/m/m1b-push/member", True),
    ("/member/events/42/ticket", True),
    ("/m/m1b-push/admin/notifications", False),
    ("/control/", False),
    ("https://evil.example/member", False),
    ("//evil.example/member", False),
    ("javascript:alert(1)", False),
    ("/member?token=secret", False),
    ("/member#fragment", False),
    ("/member\\secret", False),
    ("/member\n", False),
    ("", False),
])
def test_links_are_present_only_inside_native_contract(push_case, audience, link, accepted):
    case = push_case
    event_key = uuid4()
    expected = {"v": "3", "event_id": str(event_key), "makerspace_id": str(case.space.pk),
                "feature": "bookings", "event": "confirmed", "channel": "sw_bookings",
                "category": "sw.inbox" if audience == "member" else "sw.open"}
    title = "Your booking" if audience == "member" else None
    if accepted:
        expected["link"] = link
    if audience == "member":
        case.rendered["link"] = link
        parent = case.prepare(key=event_key)
        expected["event_id"] = str(uuid5(NAMESPACE_URL, case.envelope.dedup_key))
        send(parent.pk)
        expected["inbox_row_id"] = str(case.inbox.pk)
        expected_body = case.summary
    else:
        add_local_staff(case)
        [log] = dispatch_channel(
            makerspace=case.space, channel="native_push", feature="bookings", event="confirmed",
            text_body=case.staff_text, payload={"event_key": str(event_key), "link": link}, sync=True,
        )
        assert log.status == "sent"
        expected_body = case.staff_text
    assert len(case.calls) == 1
    assert_provider_contract(case, 0, expected, expected_body, title=title)


def test_old_staff_log_without_event_key_uses_stable_log_id(push_case):
    from apps.integrations.push import deliver_native_push

    case = push_case
    add_local_staff(case)
    log = NotificationDeliveryLog.objects.create(
        makerspace=case.space, channel="native_push", feature="bookings", event="confirmed",
        text_body=case.staff_text, payload={}, status="pending",
    )
    assert deliver_native_push(log)
    _, data = wire_message(case)
    assert data == {"v": "3", "event_id": str(log.pk), "makerspace_id": str(case.space.pk),
                    "feature": "bookings", "event": "confirmed", "channel": "sw_bookings",
                    "category": "sw.open"}
