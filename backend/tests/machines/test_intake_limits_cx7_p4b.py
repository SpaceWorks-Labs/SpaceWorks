"""Every public/staff machine target and native submission keeps the creator quotas."""
from types import SimpleNamespace

import pytest
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.machines.models import MachineServiceRequest, ServiceBucket, ServiceRequestFile
from apps.machines.public_printer_service import _kernel_payload
from apps.machines.service_storage import ServiceObjectValidationResult
from apps.payments.models import Payment
from tests.accounts.mobile_integration_helpers import APP, FIRST, PREFIX, registration
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.machines.eta_helpers import world
from tests.machines.test_job_intake import ACK, admitted
from tests.return_helpers import authenticated_client

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines, pytest.mark.area_machine_service]
KEYS = ["machine_service_open", "machine_service_submit", "machine_jobs_monthly", "print"]
KINDS = ["job", "printer", "machine", "staff_machine"]


def member_client(user, platform, settings, monkeypatch, makerspace_id=None, *, host=None):
    if platform == "browser":
        client = authenticated_client(user)
        if host is not None:
            client.defaults["HTTP_HOST"] = host
        return client
    settings.DEVICE_ATTESTATION_APPS = {}
    setattr(settings, f"DEVICE_{platform.upper()}_ATTESTATION_VERIFY_URL", "https://attest.example.test/verify")
    setattr(settings, f"DEVICE_{platform.upper()}_ATTESTATION_VERIFY_TOKEN", "provider-secret")
    identity = {"platform": platform, "app_id": APP, "environment": "production"}
    registration(**identity)
    user.set_password("strong-device-password")
    user.save(update_fields=["password"])
    client = APIClient(**({"HTTP_HOST": host} if host is not None else {}))
    challenge = client.post("/api/v1/auth/device/attestation-challenge", identity, format="json")
    assert challenge.status_code == 200
    raw = challenge.data["challenge"]
    claims = {**identity, "verified": True, "subject": f"cx7-p4b-{platform}", "challenge": raw,
              "signing_identity": PREFIX if platform == "apple" else FIRST}
    monkeypatch.setattr("apps.accounts.attestation_apple.requests.post",
                        lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: claims))
    login = client.post("/api/v1/auth/device/login", {**identity, "username": user.username,
        "password": "strong-device-password", "challenge": raw, "attestation": {"assertion": "provider-proof"}},
        format="json")
    assert login.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    if makerspace_id is not None:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}",
                           HTTP_X_MAKERSPACE_ID=str(makerspace_id))
    return client


def setup(kind, key, surface, settings, monkeypatch):
    w = world("cx7-p4b-intake", printing=True)
    member = admitted(w, "borrower")
    w.space.enabled_features = sorted((set(w.space.enabled_features) | {"machines.job_requests"})
                                      - {"charges.enabled", "charges.machines"})
    w.space.enabled_modules = [value for value in w.space.enabled_modules if value != "payments"]
    w.space.resource_limit_overrides = {key: 1}
    w.space.save(update_fields=["enabled_modules", "enabled_features", "resource_limit_overrides"])
    # These jobs ask staff to run the machine; open access is still checked by the real workflow.
    for machine in w.machines:
        machine.open_to_all_members = True
        machine.save(update_fields=["open_to_all_members"])
    if kind == "staff_machine":
        pair = callers(w.space, surface, settings, monkeypatch)
    else:
        first = member_client(member, surface, settings, monkeypatch, w.space.pk)
        second = APIClient()
        if surface == "browser":
            second = authenticated_client(member)
        else:
            second.credentials(**first._credentials)
        pair = [first, second]
    if kind == "job":
        monkeypatch.setattr("apps.machines.job_files.validate_job_object",
            lambda file: ServiceObjectValidationResult(size=10, content_type=file.content_type))
        files = [ServiceRequestFile.objects.create(makerspace=w.space, queue=w.queue, owner_user_id=member.pk,
            kind="model", object_key=f"machine-service/{w.space.pk}/part-{index}.stl",
            original_filename="part.stl", content_type="model/stl", file_policy_name="maker_formats") for index in range(2)]
        url = reverse("public-machine-job-submit", kwargs={"makerspace_slug": w.space.slug})
        bodies = [{"queue_id": w.queue.pk, "title": f"Part {index}", "file_ids": [file.pk],
                   "acknowledgements": ACK} for index, file in enumerate(files)]
    elif kind == "printer":
        url = reverse("public-printer-service-request", kwargs={"makerspace_slug": w.space.slug})
        bodies = [{"queue_id": w.queue.pk, "title": f"Part {index}"} for index in range(2)]
    else:
        url = reverse("admin-machine-service-request-list-create", kwargs={"makerspace_id": w.space.pk}) \
            if kind == "staff_machine" else reverse("public-machine-service-request-submit",
                                                   kwargs={"makerspace_slug": w.space.slug})
        bodies = [{"machine_id": w.machines[0].pk, "title": f"Part {index}",
                   "capability_payload": _kernel_payload(w.queue, {})} for index in range(2)]
        if kind == "staff_machine":
            for body in bodies:
                body["requester_id"] = member.pk
    return w, pair, url, bodies


def snapshot():
    return [list(model.objects.order_by("pk").values())
            for model in (MachineServiceRequest, ServiceBucket, ServiceRequestFile, Payment, AuditLog)]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_intake_max_next_exact_refusal_preserves_jobs_files_and_audits(kind, key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    w, pair, url, bodies = setup(kind, key, surface, settings, monkeypatch)
    assert pair[0].post(url, bodies[0], format="json").status_code == 201
    before = snapshot()
    refused = pair[1].post(url, bodies[1], format="json")
    expected = (409, "machine_jobs_monthly_quota_reached") if key == "machine_jobs_monthly" else (400, "limit_reached")
    assert (refused.status_code, refused.json()["code"]) == expected
    assert snapshot() == before
    assert MachineServiceRequest.objects.filter(makerspace=w.space).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_intake_workers_racing_at_last_slot_admit_one(kind, key, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    w, pair, url, bodies = setup(kind, key, surface, settings, monkeypatch)
    results = race_posts(pair, url, bodies)
    status, code = (409, "machine_jobs_monthly_quota_reached") if key == "machine_jobs_monthly" else (400, "limit_reached")
    assert sorted(result[0] for result in results) == sorted([201, status])
    assert [body["code"] for actual, body in results if actual == status] == [code]
    assert MachineServiceRequest.objects.filter(makerspace=w.space).count() == 1
    assert AuditLog.objects.filter(makerspace=w.space, action="machine_service.submitted").count() == 1
    assert ServiceRequestFile.objects.filter(makerspace=w.space, service_request__isnull=False).count() == (1 if kind == "job" else 0)


@pytest.mark.parametrize("kind,switch", [(kind, switch) for kind in KINDS
    for switch in ["machine_service", "machines.job_requests", "membership", "presence"]
    if kind != "staff_machine" or switch == "machine_service"])
def test_intake_switches_refuse_without_writes_then_restore(kind, switch, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    w, pair, url, bodies = setup(kind, "machine_jobs_monthly", "browser", settings, monkeypatch)
    field = "enabled_features" if "." in switch else "enabled_modules"
    saved = getattr(w.space, field)
    setattr(w.space, field, [value for value in saved if value not in ({"machine_service", "printing"}
        if switch == "machine_service" else {switch})])
    w.space.save(update_fields=[field])
    before = snapshot()
    refused = pair[0].post(url, bodies[0], format="json")
    code = "machine_intake_unavailable" if switch in {"membership", "presence"} else \
           "feature_disabled" if "." in switch else "module_disabled"
    assert (refused.status_code, refused.json()["code"]) == (404, code)
    assert snapshot() == before
    setattr(w.space, field, saved)
    w.space.save(update_fields=[field])
    assert pair[0].post(url, bodies[0], format="json").status_code == 201
    assert Payment.objects.filter(makerspace=w.space).count() == 0
