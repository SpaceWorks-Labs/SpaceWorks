"""Write docs/device-adapters/schemas/*.json from the capability registry (no Django needed)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from apps.devices.adapters import registry  # noqa: E402
from apps.devices.adapters import hello, webhook  # noqa: E402
from apps.devices.adapters.caps import (access_authorize, access_cache, artifact_upload, config_push, time_sync,  # noqa: E402
                                        checkout_kiosk, job_dispatch, locate_poses, media_snapshot,  # noqa: E402
                                        media_stream, safety, session, usage_log)

OUT = ROOT / "docs" / "device-adapters" / "schemas"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def write(name, schema):
    body = {"$schema": DRAFT, "$id": f"https://spaceworks.invalid/schemas/device-adapter/v1/{name}", **schema}
    (OUT / name).write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for cap in registry.CAPABILITIES.values():
        for command, schema in cap.commands.items():
            write(f"command.{cap.name}.{command}.json", schema)
        for event, schema in cap.events.items():
            write(f"event.{event}.json", schema)
    write("status.item.json", registry.status_schema(list(registry.CAPABILITIES)))
    write("hello.request.json", hello.HELLO)
    write("access.request.json", access_authorize.REQUEST)
    write("access.response.json", access_authorize.RESPONSE)
    write("job.ack.json", job_dispatch.ACK)
    write("job.progress.json", job_dispatch.PROGRESS)
    write("job.report.json", job_dispatch.REPORT)
    write("session.start.json", session.START)
    write("session.stop.json", session.STOP)
    write("usage.log.json", usage_log.LOG)
    write("media.signal.json", media_stream.SIGNAL)
    write("media.recording.json", media_stream.RECORDING)
    write("media.frame.json", media_snapshot.FRAME)
    write("safety.config.json", safety.CONFIG)
    write("safety.profile.json", safety.PROFILE)
    write("webhook.envelope.json", webhook.ENVELOPE)
    write("artifact.request.json", artifact_upload.REQUEST)
    write("access.cache.json", access_cache.CACHE_DOC)
    write("access.offline_decision.json", access_cache.OFFLINE_DECISION)
    write("config.ack.json", config_push.ACK)
    write("time.response.json", time_sync.RESPONSE)
    for kind, schema in locate_poses.POSE_KINDS.items():
        write(f"pose.{kind}.json", schema)
    for name in ("SESSION_START", "SCAN", "EVIDENCE", "ISSUE", "RETURN"):
        write(f"kiosk.{name.lower()}.json", getattr(checkout_kiosk, name))
    print(len(list(OUT.glob("*.json"))), "schemas")


if __name__ == "__main__":
    main()
