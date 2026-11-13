"""The shape of one capability. Pure Python (no Django) so schemas can be exported by a script."""
from dataclasses import dataclass, field

TARGET_TYPES = ("machine", "machine_type", "storage_location", "item", "box", "door", "space")
# `running` is the Fabman-style "active" (busy); `error` is a machine fault the adapter reports. `offline` is
# also derived by the server from adapter liveness.
STATES = ("idle", "preparing", "running", "paused", "finished", "failed", "error", "offline", "maintenance")


@dataclass(frozen=True)
class Capability:
    name: str
    summary: str
    targets: tuple = TARGET_TYPES
    version: int = 1
    # server -> adapter: command name -> JSON Schema of its params (delivered by lease/ack/result).
    commands: dict = field(default_factory=dict)
    # adapter -> server: event type -> JSON Schema of its data (POST events).
    events: dict = field(default_factory=dict)
    # Extra properties this capability adds to a status report item.
    status_props: dict = field(default_factory=dict)
    # Request/response routes this capability owns, for the docs and the conformance kit.
    routes: tuple = ()
    # Child switch under machines.integrations, or "".
    switch: str = ""
