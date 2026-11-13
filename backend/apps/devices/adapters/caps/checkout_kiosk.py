from ..capability import Capability
from ..schema import UUID, num, obj, text
from .access_authorize import CREDENTIAL

# The adapter is only a terminal. Every step still runs through the self-checkout workflow:
# authenticated member -> eligible scanned tool -> uploaded evidence (presigned staging) -> issue/return.
SESSION_START = obj({"binding_id": UUID, "credential": CREDENTIAL}, ["binding_id", "credential"])
SCAN = obj({"qr_payload": text(256, minLength=1)}, ["qr_payload"])
# The published ceiling is the deployment default of ``EVIDENCE_MAX_BYTES`` (10 MiB); a deployment that lowers it is
# held to the lower value by the service. Asks for a presigned STAGING upload (the final object key is never client-writable); the device PUTs the photo
# itself, then sends the returned evidence_id with issue/return.
EVIDENCE = obj({"evidence_type": {"type": "string", "enum": ["issue", "return"]},
                "content_type": text(64, minLength=3), "size_bytes": num(1, 10 * 1024 * 1024, "integer")},
               ["evidence_type", "content_type"])
ISSUE = obj({"qr_payload": text(256, minLength=1), "evidence_id": num(1, 2 ** 62, "integer")},
            ["qr_payload", "evidence_id"])
RETURN = obj({"qr_payload": text(256, minLength=1), "evidence_id": num(1, 2 ** 62, "integer"),
              "remark": text(1000, minLength=1)}, ["qr_payload", "evidence_id", "remark"])
CAPABILITY = Capability(
    "checkout.kiosk", "Public self-checkout and return through a device; never bypasses any Hard Rule.",
    targets=("space", "storage_location"), switch="machines.integrations.kiosk",
    routes=("POST kiosk/sessions", "POST kiosk/sessions/{id}/scan", "POST kiosk/sessions/{id}/evidence",
            "POST kiosk/sessions/{id}/issue", "POST kiosk/sessions/{id}/return", "DELETE kiosk/sessions/{id}"),
)
