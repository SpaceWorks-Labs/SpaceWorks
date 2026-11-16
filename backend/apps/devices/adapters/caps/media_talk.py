from ..capability import Capability
from ..schema import UUID, obj

# Two-way talk (door intercom). Staff only, push-to-talk, audited. The viewer press/release is relayed as the
# `ptt_on` / `ptt_off` signal kinds (see media_stream.SIGNAL); the adapter opens its speaker only between them.
CAPABILITY = Capability(
    "media.talk", "Staff push-to-talk toward the device speaker (door intercom). Signaling only, audited.",
    targets=("machine", "door", "space"),
    events={"media.talk_state": obj({"watch_id": UUID, "state": {"type": "string", "enum": ["open", "closed", "unavailable"]}},
                                    ["watch_id", "state"])},
    routes=("GET media/{watch_id}/signal",), switch="machines.integrations.talk",
)
