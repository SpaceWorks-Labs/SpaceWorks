"""Device Adapter API v1: the capability registry, its JSON Schemas and the validator (no DB)."""
import json
from pathlib import Path

from apps.devices.adapters import registry
from apps.devices.adapters.capability import TARGET_TYPES
from apps.devices.adapters.schema import errors

UUID = "6f1c1f0e-8f5e-4c53-9a2b-2b4d7f1e0a11"
SCHEMAS = Path(__file__).resolve().parents[4] / "docs" / "device-adapters" / "schemas"

EXPECTED = {
    "status", "telemetry", "events", "job.dispatch", "file.fetch", "control", "access.authorize", "session.start",
    "session.stop", "usage.log", "consumables", "safety", "maintenance.report", "locate.indicate",
    "locate.calibrate", "label.print", "scan.report", "sensor.report", "door.access", "media.snapshot",
    "media.stream", "checkout.kiosk", "detection.report", "time.sync",
    "media.audio", "media.talk", "artifact.upload", "telemetry.history", "diagnostics", "access.cache", "config.push",
}


def test_every_capability_is_registered_and_targets_are_known():
    assert set(registry.CAPABILITIES) == EXPECTED
    for cap in registry.CAPABILITIES.values():
        assert set(cap.targets) <= set(TARGET_TYPES), cap.name


def test_status_item_accepts_valid_and_refuses_unknown_fields():
    schema = registry.status_schema(["telemetry"])
    ok = {"binding_id": UUID, "observed_at": 1700000000, "state": "running", "progress_percent": 40}
    assert errors(schema, ok) == []
    assert errors(schema, {**ok, "state": "printing"})
    assert errors(schema, {**ok, "surprise": 1})
    # telemetry is only a property when the binding declares it
    assert errors(registry.status_schema([]), {**ok, "telemetry": {}})


def test_commands_and_events_are_schema_validated():
    assert errors(registry.command_schema("control", "power"), {"on": True}) == []
    assert errors(registry.command_schema("control", "power"), {})
    assert errors(registry.command_schema("locate.indicate", "indicate"), {"mode": "point", "duration_seconds": 5}) == []
    assert errors(registry.command_schema("locate.indicate", "indicate"), {"mode": "explode"})
    cap, schema = registry.event_schema(["scan.report"], "scan.reported")
    assert cap == "scan.report" and errors(schema, {"code_type": "qr", "value": "abc"}) == []
    assert registry.event_schema(["scan.report"], "sensor.reading") == (None, None)


def test_published_schema_files_match_the_registry():
    for cap in registry.CAPABILITIES.values():
        for command, schema in cap.commands.items():
            body = json.loads((SCHEMAS / f"command.{cap.name}.{command}.json").read_text(encoding="utf-8"))
            assert body["properties"] == schema["properties"]
        for event in cap.events:
            assert (SCHEMAS / f"event.{event}.json").exists(), event
