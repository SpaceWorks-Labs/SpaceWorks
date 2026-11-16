"""Every adapter-watch command honours the adapter's module dependency chain and video gate."""
from copy import deepcopy

import pytest

from apps.audit.models import AuditLog
from apps.devices.models import AdapterWatch
from tests.devices.test_adapter_watch_aim_credential_mod2b import watching
from tests.refusal_helpers_mod2b import refused

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("operation", ["end", "poll", "signal", "talk"])
@pytest.mark.parametrize("key", ["devices", "machines", "machine_service", "machines.integrations",
                                 "machines.integrations.video"])
def test_watch_gate_dependencies_restore_the_same_watch_without_mutating_it_while_off(operation, key, settings):
    settings.ADAPTER_TURN_URLS = []
    settings.ADAPTER_TURN_SECRET = ""
    case = watching("cx5-watch-switch", audio=True, talk=True, notice_ack=True)
    api, space = case["client"], case["space"]
    base = f"/api/v1/member/adapter-watch/{case['watch']}"
    field = "enabled_features" if "." in key else "enabled_modules"
    original = list(getattr(space, field))
    # Use the signed adapter protocol to leave a real answer waiting for viewer poll.
    adapter = case["sim"].post(f"media/{case['watch']}/signal", {"kind": "answer", "sdp": "v=0 adapter"})
    assert adapter.status_code == 201 and adapter.json() == {"n": 1}, adapter.content
    watch = AdapterWatch.objects.get(pk=case["watch"])
    original_signals = deepcopy(watch.signals)
    assert original_signals == [{"n": 1, "from": "adapter", "kind": "answer", "sdp": "v=0 adapter", "candidate": ""}]
    before = AuditLog.objects.filter(makerspace=space).count()
    setattr(space, field, [value for value in original if value != key])
    space.save(update_fields=[field])
    def call():
        if operation == "end":
            return api.delete(base)
        if operation == "poll":
            return api.get(base + "/signal")
        return api.post(base + ("/signal" if operation == "signal" else "/talk"),
            {"kind": "offer", "sdp": "v=0"} if operation == "signal" else {"active": True}, format="json")
    refused(call(), 404, "not_found")
    watch = AdapterWatch.objects.get(pk=case["watch"])
    assert watch.status == "active" and watch.ended_at is None and watch.talk_presses == 0
    assert watch.signals == original_signals
    assert AuditLog.objects.filter(makerspace=space).count() == before
    setattr(space, field, original)
    space.save(update_fields=[field])
    response = call()
    assert response.status_code == (201 if operation in {"signal", "talk"} else 200), response.content
    watch.refresh_from_db()
    if operation == "end":
        assert watch.status == "ended" and watch.ended_at is not None
        assert watch.signals == original_signals
        assert AuditLog.objects.filter(makerspace=space, action="devices.adapter_watch_ended").count() == 1
    elif operation == "talk":
        assert watch.talk_presses == 1 and response.json() == {"n": 2, "active": True}
        assert watch.signals == original_signals + [
            {"n": 2, "from": "viewer", "kind": "ptt_on", "sdp": "", "candidate": ""}]
        audits = AuditLog.objects.filter(makerspace=space, action="devices.adapter_talk_started",
            target_type="devices.device", target_id=str(case["device"].pk))
        assert audits.count() == 1
        assert audits.get().meta["watch_id"] == str(watch.pk) and audits.get().meta["press"] == 1
    else:
        if operation == "signal":
            assert response.json() == {"n": 2}
            assert watch.signals == original_signals + [
                {"n": 2, "from": "viewer", "kind": "offer", "sdp": "v=0", "candidate": ""}]
        else:
            assert response.json() == {"signals": original_signals, "ice_servers": []}
            assert watch.signals == original_signals
        assert watch.status == "active"
        assert AuditLog.objects.filter(makerspace=space).count() == before
