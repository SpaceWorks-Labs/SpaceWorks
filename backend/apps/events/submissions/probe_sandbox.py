"""Linux non-root ffprobe launcher for G's worker configuration.

Invoke: python -m apps.events.submissions.probe_sandbox <ffprobe arguments>.
G installs ffprobe and runs the worker as non-root. No network protocol is
enabled by the caller; metadata-only output is additionally capped by RLIMIT.
Exit 78 is an unavailable sandbox, distinct from a malformed input video.
"""
import os
from pathlib import Path
import shutil
import sys


def main(arguments):
    if sys.platform != "linux" or not hasattr(os, "geteuid") or os.geteuid() == 0:
        return 78
    binary = shutil.which("ffprobe")
    if not binary or not arguments:
        return 78
    for option, expected in (("-protocol_whitelist", "file,pipe"),
                             ("-format_whitelist", "mov,matroska")):
        positions = [index for index, value in enumerate(arguments)
                     if value.lstrip("-").split("=", 1)[0].split(":", 1)[0] == option[1:]]
        if len(positions) != 1:
            return 78
        position = positions[0]
        if (arguments[position] != option or position + 1 >= len(arguments) or
                arguments[position + 1] != expected):
            return 78
    local = Path(arguments[-1])
    if not local.is_absolute() or not local.is_file() or local.is_symlink():
        return 78
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 ** 2, 512 * 1024 ** 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (65536, 65536))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.execve(binary, [binary, *arguments], {"LANG": "C", "LC_ALL": "C"})
    return 78


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
