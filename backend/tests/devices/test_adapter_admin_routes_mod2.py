"""MOD-2: adapter admin routes without a direct proof: webhook rotate/deliveries, jog, shelf coverage."""

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.devices.models import AdapterCommand
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member
from tests.return_helpers import make_member, make_space
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db(transaction=True)
URL = "https://hooks.example.com/spaceworks"


@pytest.fixture(autouse=True)
def offline_push(monkeypatch):
    monkeypatch.setattr("apps.outbound_policy.is_public_https", lambda url, ports=None: url.startswith("https://"))
    monkeypatch.setattr("apps.devices.tasks.deliver_adapter_webhook_task.delay", lambda *a, **k: None)


def _with_hook(slug):
    case = adapter_case(slug)
    put = case["client"].put(reverse("devices:admin-adapter-webhook", args=[case["device"].pk]), {"url": URL},
                             format="json")
    assert put.status_code in (200, 201), put.content
    return case


def _rotate(client, case):
    return client.post(reverse("devices:admin-adapter-webhook-rotate", args=[case["device"].pk]))


def _deliveries(client, case):
    return client.get(reverse("devices:admin-adapter-webhook-deliveries", args=[case["device"].pk]))


def _feature_off(case, feature="machines.integrations"):
    space = case["space"]
    space.enabled_features = [k for k in space.enabled_features if k != feature]
    space.save(update_fields=["enabled_features"])


def test_rotate_returns_a_new_secret_once_and_bumps_the_version_with_one_audit_each():
    case = _with_hook("mod2-rot")
    first = _rotate(case["client"], case)
    second = _rotate(case["client"], case)
    assert first.status_code == 200 and second.status_code == 200
    body_a, body_b = first.json(), second.json()
    secrets = [b.get("secret") for b in (body_a, body_b)]
    assert all(secrets) and secrets[0] != secrets[1]
    assert AuditLog.objects.filter(action="devices.adapter_webhook_rotated").count() == 2
    assert case["client"].get(reverse("devices:admin-adapter-webhook", args=[case["device"].pk])).json().get(
        "secret") in (None, "")  # the secret is not readable again


def test_rotate_without_an_endpoint_is_404_and_audits_nothing():
    case = adapter_case("mod2-rot-none")
    assert _rotate(case["client"], case).status_code == 404
    assert not AuditLog.objects.filter(action="devices.adapter_webhook_rotated").exists()


def test_rotate_and_deliveries_refuse_plain_members_other_tenants_and_signed_out():
    case = _with_hook("mod2-rot-roles")
    other = adapter_case("mod2-rot-roles-other")
    member = APIClient()
    member.force_authenticate(plain_member("mod2-plain", case["space"]))
    for client in (member, other["client"], APIClient()):
        assert _rotate(client, case).status_code in (401, 403, 404)
        assert _deliveries(client, case).status_code in (401, 403, 404)
    assert not AuditLog.objects.filter(action="devices.adapter_webhook_rotated").exists()


def test_deliveries_list_is_empty_then_lists_queued_pushes_newest_first_and_capped():
    case = _with_hook("mod2-deliv")
    assert _deliveries(case["client"], case).json() == {"results": []}
    for command in ("pause", "resume"):
        queued = case["client"].post(
            reverse("devices:admin-adapter-binding-command", args=[case["binding_id"]]),
            {"capability": "control", "command": command, "params": {}}, format="json")
        assert queued.status_code == 201, queued.content
    rows = _deliveries(case["client"], case).json()["results"]
    assert len(rows) == 2 and {row["status"] for row in rows} == {"pending"}
    assert all("secret" not in row for row in rows)
    assert rows[0]["created_at"] >= rows[1]["created_at"]


def test_switching_integrations_off_refuses_rotate_and_deliveries_and_on_restores():
    case = _with_hook("mod2-rot-off")
    space = case["space"]
    features = list(space.enabled_features)
    _feature_off(case)
    assert _rotate(case["client"], case).status_code == 404
    assert _deliveries(case["client"], case).status_code == 404
    space.enabled_features = features
    space.save(update_fields=["enabled_features"])
    assert _rotate(case["client"], case).status_code == 200


JOG = "devices:admin-adapter-jog"


def _jog_case(slug):
    from tests.shelf_pointer.pointer_case import pointer_case
    case = pointer_case(slug)
    case["binding_id"] = case["pointer_binding"]
    return case


def test_jog_queues_one_calibration_command_and_audits():
    case = _jog_case("mod2-jog")
    response = case["client"].post(reverse(JOG, args=[case["binding_id"]]), {"dx": 1.5, "dy": -2}, format="json")
    assert response.status_code == 201, response.content
    command = AdapterCommand.objects.get(pk=response.json()["id"])
    assert (command.capability, command.command) == ("locate.calibrate", "jog")
    assert command.params == {"dx": 1.5, "dy": -2}


@pytest.mark.parametrize("body", [{"dx": 1001}, {"dx": -1001}, {"dy": "far"}, {"dx": 1, "extra": 1}, {"dx": None}])
def test_jog_boundaries_and_unknown_fields_are_refused_and_queue_nothing(body):
    case = _jog_case("mod2-jog-bounds")
    assert case["client"].post(reverse(JOG, args=[case["binding_id"]]), body, format="json").status_code == 400
    assert not AdapterCommand.objects.filter(binding_id=case["binding_id"], command="jog").exists()


def test_jog_edge_values_are_accepted_and_empty_body_defaults_to_zero():
    case = _jog_case("mod2-jog-edge")
    url = reverse(JOG, args=[case["binding_id"]])
    assert case["client"].post(url, {"dx": 1000, "dy": -1000}, format="json").status_code == 201
    assert case["client"].post(url, {}, format="json").status_code == 201


def test_jog_is_refused_for_plain_members_other_tenants_and_when_off():
    case = _jog_case("mod2-jog-roles")
    other = _jog_case("mod2-jog-roles-other")
    member = APIClient()
    member.force_authenticate(plain_member("mod2-jog-plain", case["space"]))
    url = reverse(JOG, args=[case["binding_id"]])
    for client in (member, other["client"], APIClient()):
        assert client.post(url, {"dx": 1}, format="json").status_code in (401, 403, 404)
    _feature_off(case)
    assert case["client"].post(url, {"dx": 1}, format="json").status_code == 404
    assert not AdapterCommand.objects.filter(binding_id=case["binding_id"], command="jog").exists()


COVERAGE = "devices:admin-shelf-coverage"


def test_shelf_coverage_reports_uncalibrated_targets_as_not_covered_and_keeps_order():
    case = _jog_case("mod2-cov")
    url = reverse(COVERAGE, args=[case["space"].pk])
    targets = [{"target_type": "item", "target_id": "1"}, {"target_type": "box", "target_id": "9"}]
    response = case["client"].post(url, {"targets": targets}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["results"] == [
        {"target_type": "item", "target_id": "1", "covered": False},
        {"target_type": "box", "target_id": "9", "covered": False}]
    assert "pose" not in str(response.json())
    assert case["client"].post(url, {"targets": []}, format="json").json() == {"results": []}


def test_shelf_coverage_limits_bad_input_roles_and_switch():
    case = _jog_case("mod2-cov-bad")
    url = reverse(COVERAGE, args=[case["space"].pk])
    one = {"target_type": "item", "target_id": "1"}
    assert case["client"].post(url, {"targets": [one] * 200}, format="json").status_code == 200
    assert case["client"].post(url, {"targets": [one] * 201}, format="json").status_code == 400
    assert case["client"].post(url, {"targets": [{"target_type": "wall", "target_id": "1"}]},
                               format="json").status_code == 400
    assert case["client"].post(url, {"targets": [{**one, "target_id": "x" * 65}]}, format="json").status_code == 400
    assert case["client"].post(url, {"targets": [one], "extra": 1}, format="json").status_code == 400
    member = APIClient()
    member.force_authenticate(plain_member("mod2-cov-plain", case["space"]))
    assert member.post(url, {"targets": [one]}, format="json").status_code == 403
    foreign = make_member("mod2-cov-foreign", make_space("mod2-cov-foreign-space"))
    stranger = APIClient()
    stranger.force_authenticate(foreign)
    assert stranger.post(url, {"targets": [one]}, format="json").status_code in (403, 404)
    assert APIClient().post(url, {"targets": [one]}, format="json").status_code in (401, 403)
    _feature_off(case)
    assert case["client"].post(url, {"targets": [one]}, format="json").status_code == 404
