"""Contract rails every Device Adapter API v1 server must hold, needing no setup beyond ``run``'s binding.

Each check sends something an adapter must never get away with (an unsigned or tampered request, an unknown body
field, an id that is not its own) and expects the documented refusal from docs/device-adapters/errors.md. Nothing
here imports Django; ``run_rails(client, binding_id)`` returns ``[(check_name, passed, detail)]`` like ``run``.
"""
import json
import time
import uuid

from tests.adapter_conformance.client import PREFIX


def _expect(results, name, condition, detail=""):
    results.append((name, bool(condition), detail))


def _code(body):
    return (body or {}).get("code") if isinstance(body, dict) else None


def _raw(client, method, route, body, headers):
    return client.transport.send(method, PREFIX + route, body, headers)


def run_rails(client, binding_id):
    results = []
    body = json.dumps({"items": []}, separators=(",", ":")).encode()
    status, _ = _raw(client, "POST", "status", body, {})
    _expect(results, "an unsigned request is refused", status in (401, 403), status)
    signed = client.headers("POST", PREFIX + "status", body)
    status, _ = _raw(client, "POST", "status", json.dumps({"items": [], "x": 1}).encode(), signed)
    _expect(results, "a body changed after signing is refused (401)", status == 401, status)

    status, body = client.post("status", {"items": [], "surprise": 1})
    _expect(results, "an unknown request field is a typed 400 invalid_payload",
            status == 400 and _code(body) == "invalid_payload", body)
    status, body = client.post("hello", {"protocol_version": 2, "adapter_kind": "generic", "capabilities": []})
    _expect(results, "an unsupported protocol_version is invalid_payload",
            status == 400 and _code(body) == "invalid_payload", body)
    status, body = client.post("access/offline-decisions", {"decisions": [], "x": 1})
    _expect(results, "offline decisions are strict too", status == 400 or status == 404, body)

    unknown = str(uuid.uuid4())
    for route, data in ((f"commands/{unknown}/ack", {"lease_token": "x" * 43, "outcome": "succeeded"}),
                        (f"jobs/{unknown}/progress", {"progress_percent": 10}),
                        (f"media/{unknown}/snapshot", {"content_type": "image/jpeg", "data": "AAAA"}),
                        ("sessions/2147483000/stop", {}),
                        ("config/ack", {"version": 999999999, "outcome": "applied"})):
        status, _ = client.post(route, data)
        _expect(results, f"POST {route.replace(unknown, '{id}')} for an id that is not ours is a 404", status == 404,
                status)
    status, _ = client.get(f"jobs/{unknown}/file")
    _expect(results, "GET jobs/{id}/file for a job that is not ours is a 404", status == 404, status)
    status, _ = client.call("DELETE", f"kiosk/sessions/{'0' * 32}")
    _expect(results, "ending a kiosk session that does not exist is a 404", status == 404, status)

    now = int(time.time())
    status, body = client.post("usage", {"operation_id": str(uuid.uuid4()), "binding_id": binding_id,
                                         "started_at": now, "ended_at": now - 60, "active_minutes": 1,
                                         "idle_minutes": 0, "outcome": "completed"})
    _expect(results, "an inverted usage record is never stored (400 invalid_range, or 404 without usage.log)",
            (status == 400 and _code(body) == "invalid_range") or status == 404, body)
    status, body = client.post("jobs/lease")
    _expect(results, "jobs/lease answers a job or null", status == 200 and "job" in (body or {}), body)
    status, body = client.get("time?nonce=rail-nonce-00000001")
    _expect(results, "signed time echoes the adapter's nonce and names its key",
            status == 200 and body["nonce"] == "rail-nonce-00000001" and isinstance(body["kid"], int)
            and len(body["signature"]) == 128, body)
    return results
