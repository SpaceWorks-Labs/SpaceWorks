"""MOD-2B: adapter camera watch (end / signal / talk), calibration aim and credential detail with exact conditions.

Every refusal asserts ONE status and ONE error code; every state change audits exactly once, a retry never twice.
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.devices.models import AdapterCommand, AdapterCredential, AdapterWatch
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member
from tests.refusal_helpers_mod2b import error_code, refused
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)
CAPS = ("status", "events", "media.stream", "media.snapshot", "media.audio", "media.talk")
SIGNED_OUT = (401, "not_authenticated")
FOREIGN = (404, "not_found")


def watching(slug, **start):
    case = adapter_case(slug, caps=CAPS)
    body = {"reason": "check", "record": False, **start}
    opened = case["client"].post(reverse("devices:admin-adapter-watch-create", args=[case["binding_id"]]), body,
                                 format="json")
    assert opened.status_code == 201, opened.content
    case["watch"] = opened.data["id"]
    return case


def off(case, feature):
    space = case["space"]
    space.enabled_features = [k for k in space.enabled_features if k != feature]
    space.save(update_fields=["enabled_features"])


def on(case, feature):
    space = case["space"]
    space.enabled_features = sorted({*space.enabled_features, feature})
    space.save(update_fields=["enabled_features"])


def watch_audits(case, action="devices.adapter_watch_ended"):
    return AuditLog.objects.filter(action=action, makerspace=case["space"]).count()


def test_ending_a_watch_audits_once_and_a_repeat_ends_nothing_and_audits_nothing_more():
    case = watching("w-end")
    url = f"/api/v1/member/adapter-watch/{case['watch']}"
    first = case["client"].delete(url)
    assert first.status_code == 200 and first.json()["status"] == "ended"
    assert watch_audits(case) == 1
    again = case["client"].delete(url)
    assert again.status_code == 200 and again.json()["status"] == "ended"
    assert watch_audits(case) == 1


def test_the_staff_end_route_audits_once_and_refuses_a_repeat_without_a_second_audit():
    case = watching("w-staff-end")
    url = reverse("devices:admin-adapter-watch-detail", args=[case["watch"]])
    assert case["client"].delete(url).status_code == 200
    assert case["client"].delete(url).status_code == 200
    assert watch_audits(case) == 1
    assert AdapterWatch.objects.get(pk=case["watch"]).status == "ended"


def test_the_viewer_routes_refuse_signed_out_a_stranger_and_another_tenant_with_exact_codes():
    case = watching("w-roles")
    other = adapter_case("w-roles-other", caps=CAPS)
    stranger = authenticated_client(plain_member("w-stranger", case["space"]))
    base = f"/api/v1/member/adapter-watch/{case['watch']}"
    for method, suffix, body in (("delete", "", None), ("get", "/signal", None),
                                 ("post", "/signal", {"kind": "offer", "sdp": "v=0"}),
                                 ("post", "/talk", {"active": True}), ("get", "/frame", None)):
        for who, expected in ((APIClient(), SIGNED_OUT), (stranger, FOREIGN), (other["client"], FOREIGN)):
            call = getattr(who, method)
            response = call(base + suffix, body, format="json") if body is not None else call(base + suffix)
            refused(response, *expected)
    assert AdapterWatch.objects.get(pk=case["watch"]).status == "active"
    assert watch_audits(case) == 0


def test_signal_validates_the_message_and_refuses_push_to_talk_kinds_on_the_signal_route():
    case = watching("w-signal")
    url = f"/api/v1/member/adapter-watch/{case['watch']}/signal"
    assert case["client"].post(url, {"kind": "banana", "sdp": "v=0"}, format="json").status_code == 400
    ptt = case["client"].post(url, {"kind": "ptt_on"}, format="json")
    assert ptt.status_code == 400 and error_code(ptt) == "invalid_payload"
    huge = case["client"].post(url, {"kind": "offer", "sdp": "x" * 200_000}, format="json")
    assert huge.status_code == 400
    assert case["client"].post(url, {"kind": "offer", "sdp": "v=0"}, format="json").status_code == 201


def test_signal_poll_on_an_ended_watch_is_a_typed_409_and_the_video_switch_off_hides_it():
    case = watching("w-ended")
    url = f"/api/v1/member/adapter-watch/{case['watch']}/signal"
    off(case, "machines.integrations.video")
    refused(case["client"].get(url), 404, "not_found")  # the watch is hidden, not announced as switched off
    on(case, "machines.integrations.video")
    assert case["client"].get(url).status_code == 200
    case["client"].delete(f"/api/v1/member/adapter-watch/{case['watch']}")
    refused(case["client"].get(url), 409, "watch_ended")
    refused(case["client"].post(url, {"kind": "offer", "sdp": "v=0"}, format="json"), 409, "watch_ended")


def test_talk_needs_a_talk_watch_the_talk_switch_and_every_press_audits_once():
    case = watching("w-talk", audio=True, talk=True, notice_ack=True)
    url = f"/api/v1/member/adapter-watch/{case['watch']}/talk"
    assert case["client"].post(url, {}, format="json").status_code == 400
    assert case["client"].post(url, {"active": "maybe"}, format="json").status_code == 400
    pressed = case["client"].post(url, {"active": True}, format="json")
    assert pressed.status_code == 201 and pressed.json()["active"] is True
    released = case["client"].post(url, {"active": False}, format="json")
    assert released.status_code == 201 and released.json()["active"] is False
    assert watch_audits(case, "devices.adapter_talk_started") == 1
    assert watch_audits(case, "devices.adapter_talk_stopped") == 1
    off(case, "machines.integrations.talk")
    refused(case["client"].post(url, {"active": True}, format="json"), 404, "not_found")  # hidden while the switch is off
    assert watch_audits(case, "devices.adapter_talk_started") == 1
    on(case, "machines.integrations.talk")
    assert case["client"].post(url, {"active": True}, format="json").status_code == 201


def test_a_watch_without_a_talk_channel_refuses_talk_with_a_403_and_no_audit():
    case = watching("w-no-talk")
    url = f"/api/v1/member/adapter-watch/{case['watch']}/talk"
    refused(case["client"].post(url, {"active": True}, format="json"), 403, "permission_denied")
    assert watch_audits(case, "devices.adapter_talk_started") == 0


def test_talk_presses_are_capped_with_a_typed_429():
    from apps.devices.services_adapter_media import MAX_PRESSES
    case = watching("w-presses", audio=True, talk=True, notice_ack=True)
    AdapterWatch.objects.filter(pk=case["watch"]).update(talk_presses=MAX_PRESSES)
    url = f"/api/v1/member/adapter-watch/{case['watch']}/talk"
    refused(case["client"].post(url, {"active": True}, format="json"), 429, "too_many_presses")
    assert watch_audits(case, "devices.adapter_talk_started") == 0
    assert case["client"].post(url, {"active": False}, format="json").status_code == 201


def _locate_case(slug):
    case = adapter_case(slug, caps=("status", "events"), extra=("locate.calibrate", "locate.indicate"))
    created = case["client"].post(reverse("devices:admin-adapter-binding-create", args=[case["device"].pk]),
                                  {"target_type": "space", "external_ref": "shelf-wall",
                                   "capabilities": ["locate.calibrate", "locate.indicate"]}, format="json")
    assert created.status_code == 201, created.content
    case["pointer"] = created.data["id"]
    return case


def test_aim_queues_one_command_validates_the_pose_and_audits_through_the_command():
    case = _locate_case("aim-ok")
    url = reverse("devices:admin-adapter-aim", args=[case["pointer"]])
    for bad in ({}, {"pose": {}}, {"pose": "left"}, {"pose": {"pan": [1]}},
                {"pose": {"pan": "x" * 5000}}):
        response = case["client"].post(url, bad, format="json")
        assert response.status_code == 400, bad
    assert not AdapterCommand.objects.filter(command="aim").exists()
    ok = case["client"].post(url, {"pose": {"pan": 1, "tilt": 2}}, format="json")
    assert ok.status_code == 201, ok.content
    assert AdapterCommand.objects.filter(command="aim", capability="locate.calibrate").count() == 1


def test_aim_refuses_signed_out_plain_member_and_other_tenant_and_the_switch_off_is_typed():
    case = _locate_case("aim-roles")
    other = _locate_case("aim-roles-other")
    url = reverse("devices:admin-adapter-aim", args=[case["pointer"]])
    body = {"pose": {"pan": 1}}
    refused(APIClient().post(url, body, format="json"), *SIGNED_OUT)
    refused(authenticated_client(plain_member("aim-plain", case["space"])).post(url, body, format="json"), 404,
            "not_found")
    refused(other["client"].post(url, body, format="json"), *FOREIGN)
    off(case, "machines.integrations")
    refused(case["client"].post(url, body, format="json"), 404, "not_found")  # the binding is hidden while off
    on(case, "machines.integrations")
    assert case["client"].post(url, body, format="json").status_code == 201
    assert AdapterCommand.objects.filter(command="aim").count() == 1


def _credential(case, user, secret="739152"):
    return case["client"].post(reverse("devices:admin-adapter-credentials", args=[case["space"].pk]),
                               {"user_id": user.pk, "kind": "pin", "secret": secret, "label": "Door"}, format="json")


def test_credential_disable_audits_once_never_leaks_the_secret_and_a_repeat_changes_nothing():
    case = adapter_case("cred-ok")
    member = plain_member("cred-member", case["space"])
    created = _credential(case, member)
    assert created.status_code == 201, created.content
    assert "secret" not in created.json() and "digest" not in created.content.decode().lower()
    row = AdapterCredential.objects.get(pk=created.json()["id"])
    url = reverse("devices:admin-adapter-credential-detail", args=[row.pk])
    first = case["client"].delete(url)
    assert first.status_code == 200 and first.json()["disabled_at"]
    audits = AuditLog.objects.filter(action="devices.adapter_credential_removed", makerspace=case["space"])
    assert audits.count() == 1
    stamp = AdapterCredential.objects.get(pk=row.pk).disabled_at
    assert case["client"].delete(url).status_code == 200
    assert audits.count() == 1 and AdapterCredential.objects.get(pk=row.pk).disabled_at == stamp


def test_credential_input_boundaries_a_three_character_pin_and_an_unknown_kind_are_refused():
    case = adapter_case("cred-bounds")
    member = plain_member("cred-bounds-member", case["space"])
    assert _credential(case, member, secret="12345").status_code == 400
    assert _credential(case, member, secret="1" * 13).status_code == 400
    assert _credential(case, member, secret="739152").status_code == 201
    bad = case["client"].post(reverse("devices:admin-adapter-credentials", args=[case["space"].pk]),
                              {"user_id": member.pk, "kind": "fingerprint", "secret": "739152"}, format="json")
    assert bad.status_code == 400
    assert AdapterCredential.objects.filter(makerspace=case["space"]).count() == 1


def test_credential_detail_refuses_signed_out_plain_member_other_tenant_and_the_access_switch_off():
    case = adapter_case("cred-roles")
    other = adapter_case("cred-roles-other")
    member = plain_member("cred-roles-member", case["space"])
    row = AdapterCredential.objects.get(pk=_credential(case, member).json()["id"])
    url = reverse("devices:admin-adapter-credential-detail", args=[row.pk])
    refused(APIClient().delete(url), *SIGNED_OUT)
    refused(authenticated_client(member).delete(url), 404, "not_found")
    refused(other["client"].delete(url), *FOREIGN)
    off(case, "machines.integrations.access")
    refused(case["client"].delete(url), 404, "not_found")  # hidden while the switch is off
    assert AdapterCredential.objects.get(pk=row.pk).disabled_at is None
    on(case, "machines.integrations.access")
    assert case["client"].delete(url).status_code == 200
