from types import SimpleNamespace
import json
import subprocess

import pytest

from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.scanning import scan
from apps.events.submissions.probing import probe_video, VideoPolicy
from apps.maker_formats.range_reader import BytesReader


class Socket:
    def __init__(self, reply):
        self.reply, self.original_reply, self.sent = reply, reply, []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def settimeout(self, value):
        assert value == 5
    def sendall(self, data):
        self.sent.append(data)
        if data == b"zVERSION\0":
            self.reply = b"ClamAV 1.4.1/12345/build-date\0"
        elif data == b"zINSTREAM\0":
            self.reply = self.original_reply
    def recv(self, maximum):
        value, self.reply = self.reply[:maximum], self.reply[maximum:]
        return value


@pytest.mark.parametrize("reply,status", [(b"stream: OK\0", "clean"), (b"stream: Eicar FOUND\0", "infected")])
def test_scanner_explicit_policy_and_streaming(reply, status):
    connection = Socket(reply)
    result = scan(BytesReader(b"content"), backend="clamav", host="configured", connect=lambda *a, **k: connection)
    assert result.status == status and b"zINSTREAM\0" in connection.sent
    assert result.version == "1.4.1/12345"
    assert connection.sent[-1] == b"\0\0\0\0"
    assert scan(BytesReader(b"content"), backend="none").status == "skipped"


@pytest.mark.parametrize("reply", [b"stream: size limit exceeded ERROR\0", b"stream: scanner failed ERROR\0", b"", b"garbage\0"])
def test_configured_scanner_can_never_fall_back_to_skip(reply):
    with pytest.raises(SubmissionError) as caught:
        scan(BytesReader(b"content"), backend="clamav", host="configured", connect=lambda *a, **k: Socket(reply))
    assert caught.value.status_code == 503


def test_probe_uses_local_protocols_bounded_wrapper_and_sanitized_output(tmp_path):
    path = tmp_path / "input.mp4"
    path.write_bytes(b"bounded fake video")
    def runner(command, **kwargs):
        assert command[0] == "sandbox-ffprobe"
        assert command[command.index("-protocol_whitelist") + 1] == "file,pipe"
        assert command[command.index("-format_whitelist") + 1] == "mov,matroska"
        assert command.count("-protocol_whitelist") == command.count("-format_whitelist") == 1
        assert kwargs["timeout"] == 20 and kwargs["shell"] is False
        kwargs["stdout"].write(json.dumps({"streams": [{"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720}],
                                          "format": {"duration": "60", "format_name": "mov,mp4"}}).encode())
        return SimpleNamespace(returncode=0)
    assert probe_video(path, sandbox_command=("sandbox-ffprobe",), run=runner)["browser_playable"]


@pytest.mark.parametrize("policy", [VideoPolicy(min_seconds=0), VideoPolicy(max_seconds=300), VideoPolicy(min_height=360)])
def test_event_video_requirements_cannot_raise_server_limits(policy):
    with pytest.raises(SubmissionError):
        policy.validate()


def test_no_probe_wrapper_is_fail_closed(tmp_path):
    path = tmp_path / "input.mp4"
    path.write_bytes(b"input")
    with pytest.raises(SubmissionError, match="video_probe_unavailable"):
        probe_video(path, sandbox_command=())


@pytest.fixture
def sandbox_probe(tmp_path, monkeypatch):
    from apps.events.submissions import probe_sandbox

    path = tmp_path / "input.mp4"
    path.write_bytes(b"input")
    monkeypatch.setattr(probe_sandbox.sys, "platform", "linux")
    monkeypatch.setattr(probe_sandbox.os, "geteuid", lambda: 10001)
    monkeypatch.setattr(probe_sandbox.shutil, "which", lambda name: "/usr/bin/ffprobe")
    monkeypatch.setattr(probe_sandbox.os, "execve", lambda *args: pytest.fail("Unexpected probe execution"))
    return probe_sandbox, str(path)


@pytest.mark.parametrize("options", [
    [],
    ["-protocol_whitelist", "file,pipe"],
    ["-format_whitelist", "mov,matroska"],
    ["-protocol_whitelist", "http", "-format_whitelist", "mov,matroska"],
    ["-protocol_whitelist", "file,pipe", "-format_whitelist", "dash"],
    ["-protocol_whitelist", "file,pipe", "-format_whitelist"],
    ["-protocol_whitelist", "file,pipe", "-format_whitelist", "mov,matroska",
     "-format_whitelist", "dash"],
    ["-protocol_whitelist", "file,pipe", "-protocol_whitelist", "http",
     "-format_whitelist", "mov,matroska"],
    ["-protocol_whitelist", "file,pipe", "-format_whitelist", "mov,matroska",
     "-format_whitelist=dash"],
    ["-protocol_whitelist", "file,pipe", "-format_whitelist", "mov,matroska",
     "--format_whitelist", "dash"],
    ["-protocol_whitelist", "file,pipe", "-format_whitelist", "mov,matroska",
     "-protocol_whitelist:0", "http"],
])
def test_sandbox_refuses_missing_wrong_or_overriding_allowlists(sandbox_probe, options):
    sandbox, path = sandbox_probe
    assert sandbox.main([*options, path]) == 78


def test_sandbox_keeps_non_root_resource_limits_and_reduced_environment(sandbox_probe, monkeypatch):
    import resource

    sandbox, path = sandbox_probe
    limits, executed = [], []
    monkeypatch.setattr(resource, "setrlimit", lambda kind, value: limits.append((kind, value)))

    class Executed(Exception):
        pass

    def execute(binary, argv, environment):
        executed.append((binary, argv, environment))
        raise Executed

    monkeypatch.setattr(sandbox.os, "execve", execute)
    options = ["-protocol_whitelist", "file,pipe", "-format_whitelist", "mov,matroska", path]
    with pytest.raises(Executed):
        sandbox.main(options)
    assert executed == [("/usr/bin/ffprobe", ["/usr/bin/ffprobe", *options], {"LANG": "C", "LC_ALL": "C"})]
    assert limits == [(resource.RLIMIT_CPU, (15, 15)),
                      (resource.RLIMIT_AS, (512 * 1024 ** 2, 512 * 1024 ** 2)),
                      (resource.RLIMIT_FSIZE, (65536, 65536)),
                      (resource.RLIMIT_NOFILE, (64, 64)), (resource.RLIMIT_CORE, (0, 0))]
