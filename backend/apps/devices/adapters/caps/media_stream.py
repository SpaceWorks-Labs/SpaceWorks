from ..capability import Capability
from ..schema import UUID, num, obj, text

SIGNAL = obj({"kind": {"type": "string", "enum": ["offer", "answer", "candidate", "bye", "ptt_on", "ptt_off"]},
              "sdp": text(16000), "candidate": text(2000)}, ["kind"])
RECORDING = obj({"content_type": text(64, minLength=3), "size_bytes": num(1, 512 * 1024 * 1024, "integer")},
                ["content_type"])
CAPABILITY = Capability(
    "media.stream", "WebRTC signaling relayed by the server; the adapter calls out. Optional TURN.",
    targets=("machine", "door", "space"),
    events={"media.stream_state": obj({"watch_id": UUID, "state": {"type": "string",
            "enum": ["connecting", "live", "ended", "fallback"]}}, ["watch_id", "state"])},
    routes=("POST media/{watch_id}/signal", "GET media/{watch_id}/signal", "POST media/{watch_id}/recording"), switch="machines.integrations.video",
)
