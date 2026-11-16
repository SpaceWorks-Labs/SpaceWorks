from ..capability import Capability
from ..schema import EPOCH, UUID, num, obj, text

# One decision made while the adapter was offline, reported on reconnect. Digest only; no member data.
OFFLINE_DECISION = obj({
    "operation_id": UUID, "binding_id": UUID, "digest": text(64, minLength=64), "allowed": {"type": "boolean"},
    "reason": text(48), "decided_at": EPOCH}, ["operation_id", "binding_id", "allowed", "decided_at"])
OFFLINE_BODY = obj({"decisions": {"type": "array", "maxItems": 100, "items": {"type": "object"}}}, ["decisions"])
CACHE_DOC = obj({"binding_id": UUID, "kid": num(1, 10 ** 6, "integer"), "version": num(1, 10 ** 12, "integer"), "issued_at": EPOCH, "expires_at": EPOCH,
                 "entries": {"type": "array", "items": obj({"digest": text(64, minLength=64), "type": {"type": "string", "enum": ["nfc"]}},
                                                         ["digest", "type"])},
                 "signature": text(128, minLength=128)},
                ["binding_id", "kid", "version", "issued_at", "expires_at", "entries", "signature"])
CAPABILITY = Capability(
    "access.cache", "Signed, expiring list of allowed NFC digests per binding for offline decisions; reconciled on reconnect.",
    targets=("machine", "door"), routes=("GET access/cache", "POST access/offline-decisions"),
    switch="machines.integrations.offline_cache",
)
