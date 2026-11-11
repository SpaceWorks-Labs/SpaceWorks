"""Original video validation. Deployment must supply the sandbox executable wrapper.

The wrapper runs ffprobe as non-root with CPU/memory/disk limits; never execute a
bare host ffprobe in a web request. Input is a bounded local temp file, not a URL.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import tempfile

from .errors import SubmissionError


@dataclass(frozen=True)
class VideoPolicy:
    min_seconds: int = 30
    max_seconds: int = 240
    min_height: int = 720
    max_width: int = 3840
    max_height: int = 2160

    def validate(self):
        if not (type(self.min_seconds) is int and type(self.max_seconds) is int and
                30 <= self.min_seconds <= self.max_seconds <= 240 and
                720 <= self.min_height <= self.max_height <= 2160 and 1280 <= self.max_width <= 3840):
            raise SubmissionError("invalid_video_policy")


def probe_video(path, *, sandbox_command, policy=VideoPolicy(), run=subprocess.run):
    policy.validate()
    local = Path(path).resolve()
    if not local.is_file() or not sandbox_command:
        raise SubmissionError("video_probe_unavailable", 503)
    command = [*sandbox_command, "-v", "error", "-protocol_whitelist", "file,pipe",
               "-format_whitelist", "mov,matroska", "-show_entries",
               "format=duration,format_name:stream=codec_type,codec_name,width,height", "-of", "json", str(local)]
    try:
        with tempfile.TemporaryFile() as output:
            response = run(command, stdin=subprocess.DEVNULL, stdout=output,
                           stderr=subprocess.DEVNULL, timeout=20, check=False, shell=False)
            if response.returncode == 78:
                raise SubmissionError("video_probe_unavailable", 503)
            output.seek(0, 2)
            if response.returncode or output.tell() > 65536:
                raise SubmissionError("invalid_video")
            output.seek(0)
            data = json.loads(output.read(65537))
        container = set(data["format"]["format_name"].split(","))
        if not container & {"mov", "mp4", "matroska", "webm"}:
            raise SubmissionError("invalid_video")
        videos = [s for s in data["streams"] if s.get("codec_type") == "video"]
        if len(videos) != 1:
            raise SubmissionError("invalid_video")
        stream = videos[0]
        width, height = int(stream["width"]), int(stream["height"])
        seconds = float(data["format"]["duration"])
        if not (policy.min_seconds <= seconds <= policy.max_seconds and
                policy.min_height <= height <= policy.max_height and 1 <= width <= policy.max_width):
            raise SubmissionError("video_limits", 413)
        codec = stream.get("codec_name", "")
        if not isinstance(codec, str) or len(codec) > 64:
            raise SubmissionError("invalid_video")
        audio = [s.get("codec_name") for s in data["streams"] if s.get("codec_type") == "audio"]
        return {"duration_seconds": seconds, "width": width, "height": height,
                "codec": codec, "browser_playable": codec in {"h264", "vp8", "vp9", "av1"} and
                all(item in {"aac", "opus", "vorbis", "mp3"} for item in audio)}
    except SubmissionError:
        raise
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SubmissionError("video_probe_unavailable", 503) from exc
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise SubmissionError("invalid_video") from exc
