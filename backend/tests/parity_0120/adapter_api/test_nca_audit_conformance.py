"""NCA-AUDIT-2 (device adapter conformance): published schemas, OpenAPI bodies and the gaps the audit closed."""
import importlib.util
import uuid
from pathlib import Path

import pytest
from django.urls import reverse

from apps.devices.adapters import registry
from apps.devices.adapters.caps import usage_log
from apps.devices.models import AdapterCommand
from apps.devices.openapi_adapter import REQUESTS, RESPONSES, openapi
from tests.parity_0120.adapter_api.adapter_case import adapter_case

REPO = Path(__file__).resolve().parents[4]
DEVICE_PREFIX = "/api/v1/device/adapter/v1/"


def _exporter():
    spec = importlib.util.spec_from_file_location("export_adapter_schemas", REPO / "scripts" / "export_adapter_schemas.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_published_schema_is_exactly_what_the_exporter_writes(tmp_path):
    """docs/device-adapters/versioning.md promises a test fails on drift: byte-for-byte, both directions."""
    exporter = _exporter()
    exporter.OUT = tmp_path
    exporter.main()
    published = REPO / "docs" / "device-adapters" / "schemas"
    fresh = {path.name: path.read_bytes() for path in tmp_path.glob("*.json")}
    # A Windows checkout (core.autocrlf) turns the committed LF into CRLF; the bytes that matter are the repo's.
    docs = {path.name: path.read_bytes().replace(b"\r\n", b"\n") for path in published.glob("*.json")}
    assert sorted(set(fresh) - set(docs)) == [], "run: python scripts/export_adapter_schemas.py"
    assert sorted(set(docs) - set(fresh)) == [], "a published schema no longer exists in code"
    assert sorted(name for name in fresh if fresh[name] != docs[name]) == []


def test_every_typed_adapter_error_code_is_documented():
    """Each literal ``AdapterError("<code>", ...)`` raised under apps/devices appears in docs/device-adapters."""
    import ast
    import re
    docs = " ".join(path.read_text(encoding="utf-8") for path in (REPO / "docs" / "device-adapters").rglob("*.md"))
    codes = set()
    for path in (REPO / "backend" / "apps" / "devices").rglob("*.py"):
        if "migrations" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) == "AdapterError"
                    and node.args and isinstance(node.args[0], ast.Constant)):
                codes.add(node.args[0].value)
    assert "invalid_payload" in codes
    assert sorted(code for code in codes if not re.search(rf"\b{re.escape(code)}\b", docs)) == []


def test_openapi_request_bodies_are_the_validator_schemas():
    assert REQUESTS["usage"]["application/json"] == openapi(usage_log.LOG)
    stop = REQUESTS["session_stop"]["application/json"]
    assert "required" not in stop and stop["additionalProperties"] is False  # OpenAPI 3.0: no empty required
    item = REQUESTS["status"]["application/json"]["properties"]["items"]["items"]
    assert item["properties"]["interlocks"]["properties"]["filter_ok"] == {"type": "boolean", "nullable": True}
    assert set(item["properties"]) == set(registry.status_schema(list(registry.CAPABILITIES))["properties"])
    assert all(schema.get("additionalProperties") is not False for name, schema in RESPONSES.items()
               if name not in ("access_cache", "time"))  # adapters must ignore unknown response fields


@pytest.fixture(scope="module")
def document():
    from drf_spectacular.drainage import GENERATOR_STATS
    from drf_spectacular.generators import SchemaGenerator
    GENERATOR_STATS.reset()
    return SchemaGenerator().get_schema(request=None, public=True)


def test_every_staff_and_viewer_adapter_operation_passes_the_contract_guard(document):
    """The console and job-owner routes (admin/adapter*, member/adapter-*, adapter-profile, shelf pointer)."""
    from apps.openapi_contract.check import contract_failures
    paths = {path: item for path, item in document["paths"].items()
             if not path.startswith(DEVICE_PREFIX) and ("adapter" in path or "shelf" in path)}
    assert len(paths) >= 30
    assert contract_failures({**document, "paths": paths}) == []
    signal = paths["/api/v1/member/adapter-watch/{id}/signal"]["post"]
    assert signal["requestBody"]["content"]["application/json"]["schema"]["properties"]["kind"]["enum"][0] == "offer"


def test_every_device_adapter_operation_passes_the_contract_guard(document):
    from apps.openapi_contract.check import contract_failures
    adapter_paths = {path: item for path, item in document["paths"].items() if path.startswith(DEVICE_PREFIX)}
    assert len(adapter_paths) >= 31
    failures = contract_failures({**document, "paths": adapter_paths})
    assert failures == []
    assert "201" in adapter_paths[DEVICE_PREFIX + "kiosk/sessions"]["post"]["responses"]
    hello = adapter_paths[DEVICE_PREFIX + "hello"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert hello["properties"]["adapter_kind"]["enum"] == list(registry.KINDS)


@pytest.mark.django_db(transaction=True)
def test_job_progress_and_report_are_404_once_the_switch_is_off():
    from tests.parity_0120.adapter_api.test_job_dispatch import dispatched, lease_and_ack
    case = dispatched("nca-job-off")
    job = lease_and_ack(case)
    space = case["space"]
    space.enabled_features = [key for key in space.enabled_features if not key.startswith("machines.integrations")]
    space.save(update_fields=["enabled_features"])
    assert case["sim"].post(f"jobs/{job['job_id']}/progress", {"progress_percent": 50}).status_code == 404
    report = {"operation_id": str(uuid.uuid4()), "outcome": "completed", "actual_minutes": 3, "consumptions": []}
    assert case["sim"].post(f"jobs/{job['job_id']}/report", report).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_a_command_whose_child_switch_went_off_is_never_leased():
    case = adapter_case("nca-cmd-off", caps=("status", "events", "control", "media.snapshot"))
    url = reverse("devices:admin-adapter-binding-command", args=[case["binding_id"]])
    snapshot = case["client"].post(url, {"capability": "media.snapshot", "command": "snapshot",
                                         "params": {"watch_id": str(uuid.uuid4())}}, format="json")
    assert snapshot.status_code == 201, snapshot.data
    pause = case["client"].post(url, {"capability": "control", "command": "pause", "params": {}}, format="json")
    assert pause.status_code == 201, pause.data
    space = case["space"]
    space.enabled_features = [key for key in space.enabled_features if key != "machines.integrations.video"]
    space.save(update_fields=["enabled_features"])
    leased = case["sim"].post("commands/lease")
    assert leased.status_code == 200 and leased.data["command"]["command"] == "pause", leased.data
    refused = AdapterCommand.objects.get(pk=snapshot.data["id"])
    assert refused.status == AdapterCommand.Status.FAILED and refused.result_code == "capability_switched_off"


@pytest.mark.django_db(transaction=True)
def test_kiosk_evidence_of_a_disallowed_type_is_a_typed_400(settings):
    from tests.parity_0120.adapter_api.test_kiosk_checkout import kiosk, start, step
    settings.API_CLIENT_AUTH_REQUIRED = False
    case = kiosk("nca-kiosk-type")
    opened = start(case)
    assert opened.status_code == 201 and opened.data["allowed"] is True, opened.data
    response = step(case, opened.data["session_id"], "evidence", {"evidence_type": "issue", "content_type": "image/gif"})
    assert response.status_code == 400 and response.data["code"] == "content_type_not_allowed", response.data
