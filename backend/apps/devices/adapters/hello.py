"""The hello contract: what an adapter declares about itself right after enrollment (and on every restart)."""
from .registry import KINDS
from .schema import num, obj, text

CAPABILITY_DECLARATION = obj({"name": text(32, minLength=1), "version": num(1, 99, "integer")}, ["name"])
# The server answers hello with ``cache_keys``: [{kid, public_key (base64 Ed25519), status: current|previous}].
HELLO = obj({
    "protocol_version": num(1, 1, "integer"),
    "adapter_kind": {"type": "string", "enum": list(KINDS)},
    "vendor": text(80), "software_version": text(40), "firmware": text(40),
    "health": {"type": "string", "enum": ["ok", "degraded", "failing"]},
    "capabilities": {"type": "array", "items": CAPABILITY_DECLARATION, "maxItems": 32},
    "config_version_seen": num(0, 10 ** 9, "integer"),
}, ["protocol_version", "adapter_kind", "capabilities"])
