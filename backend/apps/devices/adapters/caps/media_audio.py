from ..capability import Capability
from ..schema import UUID, obj

# Audio is an extra track on the existing media.stream WebRTC session; RECEIVE-ONLY (adapter -> viewer) by default.
# The viewer opts in per watch; audio recording is a separate capability switch with its own notice and retention.
CAPABILITY = Capability(
    "media.audio", "An audio track on the media.stream session (receive-only). Needs media.stream on the same binding.",
    targets=("machine", "door", "space"),
    events={"media.audio_state": obj({"watch_id": UUID, "state": {"type": "string", "enum": ["muted", "live", "unavailable"]}},
                                     ["watch_id", "state"])},
    routes=("GET media/{watch_id}/signal",), switch="machines.integrations.audio",
)
