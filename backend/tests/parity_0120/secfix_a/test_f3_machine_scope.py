"""SECURITY-REVIEW M5 / decision 336(i): adapter-level staff routes honour the reader's machine scope.

Only a Space Manager holds MANAGE_DEVICES in the fixed catalogue, and a Space Manager is unrestricted, so a narrowed
reader is simulated by narrowing ONE manager's resolved machine scope to the first machine's type (the same resolver
``can_manage_machine`` and ``covers_type`` read). The unnarrowed manager is the normal case on every route.
"""
import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.devices.models import AdapterAccessLog, AdapterBinding, AdapterCommand, AdapterEvent, AdapterUsageLog
from tests.devices.helpers import staff_client
from tests.parity_0120.adapter_api.adapter_case import adapter_case
from tests.test_machine_service_workflow import machine

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def narrowed(monkeypatch):
    """``{user_id: (type ids, machine ids)}``: those users' machine scope is exactly that; everyone else unchanged."""
    from apps.machines import role_scope_resolution as resolution
    original, scopes = resolution.manage_scope_for, {}

    def manage_scope_for(actor, makerspace_id):
        if getattr(actor, "pk", None) in scopes:
            return scopes[actor.pk]
        return original(actor, makerspace_id)

    monkeypatch.setattr(resolution, "manage_scope_for", manage_scope_for)
    return scopes


def _world(slug, narrowed):
    case = adapter_case(slug)
    other = machine(case["space"], name="Laser Y")
    bound = case["client"].post(reverse("devices:admin-adapter-binding-create", args=[case["device"].pk]),
                                {"target_type": "machine", "machine_id": other.pk, "capabilities": ["control"]},
                                format="json")
    assert bound.status_code == 201, bound.data
    reader, client = staff_client(case["space"], f"{slug}-scoped")
    narrowed[reader.pk] = (frozenset({case["machine"].machine_type_id}), frozenset())
    case.update(other=other, other_binding_id=bound.data["id"], reader=reader, reader_client=client)
    return case


def _rows(case):
    """One access log, usage log, event and command per binding, plus an access log and event with no binding."""
    device, space, now = case["device"], case["space"], timezone.now()
    out = {}
    for key, binding_id in (("mine", case["binding_id"]), ("other", case["other_binding_id"]), ("gone", None)):
        binding = AdapterBinding.objects.get(pk=binding_id) if binding_id else None
        out[key] = {
            "access": AdapterAccessLog.objects.create(makerspace=space, device=device, binding=binding,
                                                      credential_type="nfc", allowed=False, reason="unknown_credential"),
            "event": AdapterEvent.objects.create(makerspace=space, device=device, binding=binding,
                                                 operation_id=uuid.uuid4(), event_type="machine.state",
                                                 capability="status", observed_at=now),
        }
        if binding is not None:
            out[key]["usage"] = AdapterUsageLog.objects.create(
                makerspace=space, device=device, binding=binding, operation_id=uuid.uuid4(), started_at=now,
                ended_at=now, outcome="completed")
            out[key]["command"] = AdapterCommand.objects.create(
                makerspace=space, device=device, binding=binding, device_key_version=device.key_version,
                capability="control", command="pause", expires_at=now + timedelta(minutes=5))
    return out


def _ids(data):
    rows = data["results"] if isinstance(data, dict) else data
    return {str(row["id"]) for row in rows}


def _get(client, name, case):
    return client.get(reverse(f"devices:{name}", args=[case["device"].pk]))


def test_logs_events_and_commands_are_narrowed_to_the_readers_machines(narrowed):
    case = _world("f3-scope-logs", narrowed)
    rows = _rows(case)
    for name, kind, keys in (("admin-adapter-access-decisions", "access", ("mine", "other", "gone")),
                             ("admin-adapter-usage", "usage", ("mine", "other")),
                             ("admin-adapter-events", "event", ("mine", "other", "gone")),
                             ("admin-adapter-commands", "command", ("mine", "other"))):
        scoped = _get(case["reader_client"], name, case)
        assert scoped.status_code == 200, (name, scoped.data)
        # Attack: the out-of-scope machine's rows and the unattributable (unbound) rows stay hidden.
        seen = _ids(scoped.data)
        assert str(rows["mine"][kind].pk) in seen, name
        assert not seen & {str(rows[key][kind].pk) for key in keys if key != "mine"}, name
        full = _get(case["client"], name, case)
        assert full.status_code == 200
        # Normal: the unrestricted Space Manager still reads every row.
        assert {str(rows[key][kind].pk) for key in keys} <= _ids(full.data), name


def test_the_adapter_picture_lists_only_bindings_in_scope(narrowed):
    case = _world("f3-scope-summary", narrowed)
    detail = case["reader_client"].get(reverse("devices:admin-adapter-detail", args=[case["device"].pk]))
    assert detail.status_code == 200
    assert {row["id"] for row in detail.data["bindings"]} == {case["binding_id"]}
    listing = case["reader_client"].get(reverse("devices:admin-adapter-list", args=[case["space"].pk]))
    assert {row["id"] for row in listing.data["results"][0]["bindings"]} == {case["binding_id"]}
    full = case["client"].get(reverse("devices:admin-adapter-detail", args=[case["device"].pk]))
    assert {row["id"] for row in full.data["bindings"]} == {case["binding_id"], case["other_binding_id"]}


def test_config_push_and_the_push_endpoint_need_every_machine_in_scope(narrowed):
    case = _world("f3-scope-config", narrowed)
    url = reverse("devices:admin-adapter-config-versions", args=[case["device"].pk])
    refused = case["reader_client"].post(url, {"config": {"poll_seconds": 5}}, format="json")
    assert refused.status_code == 403
    assert case["reader_client"].get(url).status_code == 403
    hook = reverse("devices:admin-adapter-webhook", args=[case["device"].pk])
    assert case["reader_client"].get(hook).status_code == 403
    assert case["reader_client"].delete(hook).status_code == 403
    # Normal: the unrestricted manager pushes; and a reader whose scope covers both machines may too.
    assert case["client"].post(url, {"config": {"poll_seconds": 5}}, format="json").status_code == 201
    narrowed[case["reader"].pk] = (frozenset({case["machine"].machine_type_id, case["other"].machine_type_id}),
                                   frozenset())
    assert case["reader_client"].post(url, {"config": {"poll_seconds": 6}}, format="json").status_code == 201
    assert case["reader_client"].get(hook).status_code != 403


def test_a_type_safety_profile_needs_authority_over_that_type(narrowed):
    case = _world("f3-scope-profile", narrowed)
    url = reverse("devices:admin-adapter-type-profile",
                  args=[case["space"].pk, case["other"].machine_type_id])
    assert case["reader_client"].put(url, {"max_session_minutes": 1440}, format="json").status_code == 403
    assert case["reader_client"].get(url).status_code == 404
    mine = reverse("devices:admin-adapter-type-profile", args=[case["space"].pk, case["machine"].machine_type_id])
    assert case["reader_client"].put(mine, {"max_session_minutes": 60}, format="json").status_code == 200
    assert case["client"].put(url, {"max_session_minutes": 90}, format="json").status_code == 200


def test_a_foreign_binding_is_the_same_404_as_a_missing_one_for_jobs_and_locate():
    """L-A6: dispatch and shelf-pointer staff routes resolve the binding inside the actor's scope first."""
    case = adapter_case("f3-oracle-home")
    foreign = adapter_case("f3-oracle-away")  # adapters ON there: the old path answered 403 (no MANAGE_DEVICES)
    client = case["client"]
    job_url = lambda pk: reverse("devices:admin-adapter-job-create", args=[pk])  # noqa: E731
    pose_url = lambda pk: reverse("devices:admin-adapter-poses", args=[pk])  # noqa: E731
    for missing, other in (
        (client.post(job_url(uuid.uuid4()), {"service_request_id": 1}, format="json"),
         client.post(job_url(foreign["binding_id"]), {"service_request_id": 1}, format="json")),
        (client.get(pose_url(uuid.uuid4())), client.get(pose_url(foreign["binding_id"]))),
    ):
        assert missing.status_code == other.status_code == 404, (missing.status_code, other.status_code)
    # Normal: the home binding is reached and refused only for its own reason (it serves neither capability).
    assert client.post(job_url(case["binding_id"]), {"service_request_id": 1}, format="json").status_code == 409
    assert client.get(pose_url(case["binding_id"])).status_code == 409


def test_an_anonymous_caller_is_refused_before_any_scope_check():
    case = adapter_case("f3-anon")
    assert APIClient().get(reverse("devices:admin-adapter-access-decisions",
                                   args=[case["device"].pk])).status_code == 401
