"""The in-repo MOCK adapter: a tiny reference implementation of Device Adapter API v1 (tests and docs only).

It declares status, events, control, access.authorize and usage.log, reports status, leases and acknowledges
commands, and records what it was told to do so a conformance run can assert the round trip. It is the smallest
thing that is a conforming adapter; a vendor adapter in another repo follows the same loop.
"""
import time
import uuid

CAPABILITIES = ("status", "events", "control", "access.authorize", "usage.log", "job.dispatch", "file.fetch",
                "checkout.kiosk", "media.stream", "media.snapshot", "label.print", "media.audio", "media.talk",
                "artifact.upload", "detection.report", "telemetry.history", "diagnostics", "access.cache", "config.push",
                "time.sync")


class MockAdapter:
    def __init__(self, client, binding_id=None):
        self.client, self.binding_id = client, binding_id
        self.received = []  # commands this adapter executed, in order

    def hello(self):
        return self.client.post("hello", {
            "protocol_version": 1, "adapter_kind": "generic", "vendor": "spaceworks-mock", "software_version": "1",
            "capabilities": [{"name": name, "version": 1} for name in CAPABILITIES]})

    def report_status(self, state="idle", **extra):
        return self.client.post("status", {"items": [
            {"binding_id": self.binding_id, "observed_at": int(time.time()), "state": state, **extra}]})

    def send_event(self, event_type, data, operation_id=None):
        return self.client.post("events", {"events": [{
            "operation_id": operation_id or str(uuid.uuid4()), "binding_id": self.binding_id, "type": event_type,
            "observed_at": int(time.time()), "data": data}]})

    def authorize(self, credential):
        return self.client.post("access/authorize", {"binding_id": self.binding_id, "credential": credential})

    def lease_job(self, external_job_id="mock-job-1"):
        """job.dispatch: lease the next job and acknowledge it with the vendor's own job id. None if nothing queued."""
        status, body = self.client.post("jobs/lease")
        job = (body or {}).get("job") if status == 200 else None
        if job is None:
            return None
        self.client.post(f"jobs/{job['job_id']}/ack", {"lease_token": job["lease_token"],
                                                     "external_job_id": external_job_id})
        return job

    def report_job(self, job, minutes=10, consumptions=()):
        body = {"operation_id": str(uuid.uuid4()), "outcome": "completed", "actual_minutes": minutes,
                "consumptions": list(consumptions)}
        return body, self.client.post(f"jobs/{job['job_id']}/report", body)

    def kiosk_start(self, binding_id, credential):
        return self.client.post("kiosk/sessions", {"binding_id": binding_id, "credential": credential})

    def kiosk_evidence(self, session_id, kind="issue", content_type="image/jpeg"):
        return self.client.post(f"kiosk/sessions/{session_id}/evidence",
                                {"evidence_type": kind, "content_type": content_type})

    def signal(self, watch_id, kind, **fields):
        return self.client.post(f"media/{watch_id}/signal", {"kind": kind, **fields})

    # --- decision 321: media and data capabilities -------------------------------------------------------------
    def request_artifact(self, kind="thumbnail", content_type="image/jpeg", size_bytes=1024, **links):
        return self.client.post("artifacts", {"operation_id": str(uuid.uuid4()), "binding_id": self.binding_id,
                                              "kind": kind, "content_type": content_type, "size_bytes": size_bytes,
                                              **links})

    def complete_artifact(self, artifact_id):
        return self.client.post(f"artifacts/{artifact_id}/complete", {})

    def report_detection(self, kind="failure", confidence=0.9, **extra):
        return self.send_event("detection.reported", {"kind": kind, "confidence": confidence, **extra})

    def fetch_access_cache(self):
        return self.client.get(f"access/cache?binding_id={self.binding_id}")

    def report_offline_decision(self, digest, allowed, decided_at=None):
        return self.client.post("access/offline-decisions", {"decisions": [{
            "operation_id": str(uuid.uuid4()), "binding_id": self.binding_id, "digest": digest, "allowed": allowed,
            "decided_at": int(decided_at or time.time())}]})

    def fetch_config(self):
        return self.client.get("config")

    def ack_config(self, version, outcome="applied"):
        return self.client.post("config/ack", {"version": version, "outcome": outcome})

    def server_time(self, nonce="mock-adapter-nonce-0001"):
        return self.client.get(f"time?nonce={nonce}")

    def poll_once(self, outcome="succeeded"):
        """Lease one command, 'execute' it (record it), acknowledge it. Returns the command or None."""
        status, body = self.client.post("commands/lease")
        command = (body or {}).get("command") if status == 200 else None
        if command is None:
            return None
        self.received.append((command["capability"], command["command"], command["params"]))
        self.client.post(f"commands/{command['command_id']}/ack",
                         {"lease_token": command["lease_token"], "outcome": outcome})
        return command
