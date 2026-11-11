"""The backend image ships a source-built, pinned ffprobe, never Debian's ffmpeg (decision 222b)."""
import re
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"


def _text():
    return DOCKERFILE.read_text(encoding="utf-8")


def test_no_debian_ffmpeg_package_is_installed():
    for line in _text().splitlines():
        code = line.split("#", 1)[0]
        assert not re.search(r"(^|\s)(ffmpeg|libav\w*|libxml2)(\s|\|$)", code), line


def test_ffprobe_is_built_from_a_pinned_checksummed_source_release():
    text = _text()
    assert re.search(r"ARG FFMPEG_VERSION=\d+\.\d+(\.\d+)?\n", text)
    assert re.search(r"ARG FFMPEG_SHA256=[0-9a-f]{64}\n", text)
    assert "sha256sum -c" in text
    assert "COPY --from=ffprobe-build /build/ffprobe /usr/local/bin/ffprobe" in text
    assert 'LABEL spaceworks.ffmpeg.version="${FFMPEG_VERSION}"' in text


def test_ffprobe_is_configured_minimally():
    text = _text()
    for flag in ("--disable-everything", "--disable-autodetect", "--disable-network",
                 "--disable-doc", "--enable-ffprobe", "--disable-ffmpeg",
                 "--enable-demuxer=mov,matroska", "--enable-protocol=file,pipe"):
        assert flag in text
    assert "--enable-libxml2" not in text
