from ..capability import Capability
from ..schema import num, obj, text

RESPONSE = obj({"server_time": num(0, 4102444800, "integer"), "nonce": text(64, minLength=16), "kid": num(1, 10 ** 6, "integer"),
                "signature": text(128, minLength=128)}, ["server_time", "nonce", "kid", "signature"])
CAPABILITY = Capability(
    "time.sync", "A signed server time (Ed25519 over the framed time-v1 domain, nonce, kid and time; the adapter "
    "sends a fresh 16-64 char nonce; verify with the public keys from hello).",
    routes=("GET time",),
)
