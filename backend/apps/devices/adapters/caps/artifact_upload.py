from ..capability import Capability
from ..schema import EPOCH, UUID, num, obj, text

KINDS = ("timelapse", "thumbnail", "preview", "failure_snapshot", "log_bundle", "audio_recording")
# Per-kind size cap (bytes) and default retention (days); the deployment may override retention in settings.
LIMITS = {"timelapse": (256 * 2 ** 20, 30), "thumbnail": (5 * 2 ** 20, 90), "preview": (5 * 2 ** 20, 90),
          "failure_snapshot": (5 * 2 ** 20, 30), "log_bundle": (10 * 2 ** 20, 7), "audio_recording": (64 * 2 ** 20, 3)}
REQUEST = obj({
    "operation_id": UUID, "binding_id": UUID, "kind": {"type": "string", "enum": list(KINDS)},
    "content_type": text(64, minLength=3), "size_bytes": num(1, 256 * 2 ** 20, "integer"),
    "service_request_id": num(1, 10 ** 12, "integer"), "session_id": num(1, 10 ** 12, "integer"),
    "command_id": UUID, "captured_at": EPOCH,
}, ["operation_id", "binding_id", "kind", "content_type", "size_bytes"])
CAPABILITY = Capability(
    "artifact.upload", "Adapter-uploaded timelapses, job thumbnails/previews and failure snapshots (private, retention-limited).",
    targets=("machine",), routes=("POST artifacts", "POST artifacts/{id}/complete"), switch="machines.integrations.artifacts",
)
