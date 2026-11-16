"""Claim policy for the camera-watch, artifact and detection routes a job owner uses on a machine.

A claim session (a walk-in claiming an account at a kiosk) never watches, relays or reads a member's
machine camera, recordings or detections; only a signed-in person acting on their own job does.
"""

from apps.accounts.claim_route_types import AnonymousRead, Refused

_REASON = "claim sessions cannot watch a machine camera"
_ROUTES = (
    ("devices:member-adapter-watch-start", ("POST",)),
    ("devices:member-adapter-watch-end", ("DELETE",)),
    ("devices:member-adapter-watch-signal", ("GET", "HEAD", "POST")),
    ("devices:member-adapter-watch-frame", ("GET", "HEAD")),
    ("devices:member-adapter-watch-talk", ("POST",)),
    ("devices:member-adapter-artifacts", ("GET", "HEAD")),
    ("devices:member-adapter-artifact-url", ("GET", "HEAD")),
    ("devices:member-adapter-detections", ("GET", "HEAD")),
)

ADAPTER_WATCH_CLAIM_ROUTES = {
    **{(name, method): Refused(_REASON) for name, methods in _ROUTES for method in methods},
    **{(name, "OPTIONS"): AnonymousRead() for name, _methods in _ROUTES},
}
