"""Conformance checks for Device Adapter API v1: run them against ANY server (a dev stack, or your own build).

``run(client, binding_id)`` returns ``[(check_name, passed, detail)]``. The server needs `machines.integrations`
on for the space, an enrolled adapter device and one binding that serves status, events and control; a staff user
queues a ``control/pause`` command for the binding before the lease check (the CLI prints what to do, see
docs/device-adapters/build-an-adapter.md). Nothing here imports Django.
"""
import time
import uuid

from tests.adapter_conformance.mock_adapter import MockAdapter


def _expect(results, name, condition, detail=""):
    results.append((name, bool(condition), detail))


def _code(body):
    return (body or {}).get("code") if isinstance(body, dict) else None


def run(client, binding_id, *, expect_command=False):
    results, adapter = [], MockAdapter(client, binding_id)
    status, hello = adapter.hello()
    _expect(results, "hello returns 200 with protocol_version 1 and the accepted capabilities",
            status == 200 and hello and hello["protocol_version"] == 1 and hello["unknown_capabilities"] == [], status)
    _expect(results, "hello lists this adapter's bindings",
            any(row["id"] == binding_id for row in (hello or {}).get("bindings", [])))
    status, body = client.get("bindings")
    _expect(results, "GET bindings is signed and returns bindings", status == 200 and "bindings" in (body or {}), status)

    status, body = adapter.report_status("idle", progress_percent=0)
    _expect(results, "status accepted (stored, stale or throttled)", status == 200 and body["results"][0]["result"]
            in ("stored", "stale", "throttled"), body)
    status, body = client.post("status", {"items": [{"binding_id": binding_id, "observed_at": int(time.time()),
                                                     "state": "printing"}]})
    _expect(results, "an unknown state is a typed 400 invalid_payload",
            status == 400 and body["code"] == "invalid_payload", body)

    operation = str(uuid.uuid4())
    first = adapter.send_event("adapter.note", {"message": "conformance"}, operation)
    second = adapter.send_event("adapter.note", {"message": "conformance"}, operation)
    _expect(results, "events are idempotent by operation_id",
            first[1]["results"][0]["result"] == "stored" and second[1]["results"][0]["result"] == "duplicate",
            (first, second))
    status, body = adapter.send_event("sensor.reading", {"sensor": "x", "value": 1})
    _expect(results, "an event of an undeclared capability is refused with event_not_declared",
            status == 400 and body["code"] == "event_not_declared", body)

    nonce = "AAAAAAAAAAAAAAAAAAAAAA"
    client.post("status", {"items": []}, nonce=nonce)
    status, _body = client.post("status", {"items": []}, nonce=nonce)
    _expect(results, "a replayed nonce is refused (401)", status == 401, status)
    status, _body = client.post("status", {"items": []}, timestamp=int(time.time()) - 3600)
    _expect(results, "a stale timestamp is refused (401)", status == 401, status)

    # Safety rails every adapter must see: a job report before its ack, and a kiosk step without a session, are refused.
    status, body = client.post(f"jobs/{uuid.uuid4()}/report", {"operation_id": str(uuid.uuid4()), "outcome": "completed",
                                                              "actual_minutes": 1, "consumptions": []})
    _expect(results, "a report for an unknown job is a 404, never a 2xx", status == 404, status)
    status, _body = client.post(f"kiosk/sessions/{'0' * 32}/issue", {"qr_payload": "x", "evidence_id": 1})
    _expect(results, "a kiosk issue without a live session is a 404 (no evidence bypass)", status == 404, status)
    status, body = client.post("kiosk/sessions", {"binding_id": binding_id})
    _expect(results, "a kiosk session without a credential is a typed 400", status in (400, 404), status)
    status, _body = client.post(f"media/{uuid.uuid4()}/signal", {"kind": "offer", "sdp": "v=0"})
    _expect(results, "signaling for an unknown watch is a 404", status == 404, status)

    if expect_command:
        command = adapter.poll_once()
        _expect(results, "a queued control command is leased, executed and acknowledged",
                command is not None and command["capability"] == "control", command)
    return results


def verify_ed25519(cache_keys, kid, message, signature):
    """What an adapter does with the PUBLIC keys from its hello response: pick the key by ``kid`` and verify.

    Only keys listed by the server are trusted (current, or previous during rotation); an unknown kid is a failure.
    """
    from apps.ed25519 import Ed25519Error, decode_key, verify_bytes
    key = next((row for row in cache_keys if row["kid"] == kid), None)
    if key is None:
        return False
    try:
        raw = message if isinstance(message, bytes) else message.encode()
        verify_bytes(raw, bytes.fromhex(signature), decode_key(key["public_key"], label="public key", length=32))
    except (Ed25519Error, ValueError):
        return False
    return True


def framed(domain, *fields):
    """The documented signing frame (media-and-data.md), written independently of the server code: the ASCII domain,
    one NUL byte, then per field a 4-byte big-endian length and the field's UTF-8 text."""
    out = domain.encode("ascii") + bytes([0])
    for field in fields:
        raw = str(field).encode("utf-8")
        out += len(raw).to_bytes(4, "big") + raw
    return out


def cache_message(document, digests):
    import hashlib
    fingerprint = hashlib.sha256(",".join(sorted(digests)).encode()).hexdigest()
    return framed("spaceworks-adapter-offline-cache-v1", document["binding_id"], document["kid"], document["version"],
                  document["issued_at"], document["expires_at"], fingerprint)


def time_message(nonce, kid, server_time):
    return framed("spaceworks-adapter-time-v1", nonce, kid, server_time)


def run_media(client, binding_id, cache_keys):
    """Media/data checks (decision 321). Needs the child switches on and a binding serving the capabilities.

    ``cache_keys`` is the ``cache_keys`` list of the hello response (public keys only)."""
    results, adapter = [], MockAdapter(client, binding_id)
    status, body = adapter.server_time("conformance-nonce")
    _expect(results, "signed time verifies with a public key from hello", status == 200 and verify_ed25519(
        cache_keys, body["kid"], time_message("conformance-nonce", body["kid"], body["server_time"]), body["signature"]),
        body)
    status, body = adapter.server_time("short")
    _expect(results, "signed time refuses a nonce that is not 16-64 chars (400 invalid_nonce)",
            status == 400 and _code(body) == "invalid_nonce", body)
    status, body = adapter.fetch_config()
    _expect(results, "config fetch returns a version and an object", status == 200 and isinstance(body["config"], dict), body)
    status, body = adapter.request_artifact("timelapse", "image/jpeg")
    _expect(results, "a content type not allowed for the kind is a 400", status == 400, body)
    status, body = adapter.request_artifact("thumbnail", size_bytes=10 ** 9)
    _expect(results, "an oversize artifact is refused before any upload is issued", status in (400, 413), body)
    status, body = adapter.complete_artifact(uuid.uuid4())
    _expect(results, "completing an unknown artifact is a 404", status == 404, status)
    status, body = adapter.report_detection("failure", 1.5)
    _expect(results, "a detection confidence above 1 is a typed 400", status == 400, body)
    status, body = adapter.fetch_access_cache()
    if status == 200:
        document = body
        digests = [row["digest"] for row in document["entries"]]
        _expect(results, "the offline access cache is Ed25519-signed, names its kid and expires",
                verify_ed25519(cache_keys, document["kid"], cache_message(document, digests), document["signature"])
                and document["expires_at"] > document["issued_at"], document)
        forged = {**document, "kid": 999}
        _expect(results, "a cache naming an unknown kid is rejected by the adapter",
                not verify_ed25519(cache_keys, forged["kid"], cache_message(forged, digests), document["signature"]))
    return results


def report(results):
    width = max(len(name) for name, _ok, _detail in results)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}" + ("" if ok else f"  -> {detail}"))
    return all(ok for _name, ok, _detail in results)
