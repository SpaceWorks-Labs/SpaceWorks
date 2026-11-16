"""Drive the real setup questionnaire prompt by prompt (local helper, not a test).

Usage: python tests/drive_questionnaire.py '{"Use Events?": "y"}' [edition]
Every prompt not named gets its default (Enter). Prints the summary and areas.json.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
NAMES = ("setup-questions.sh", "setup-question-input.sh", "setup-area-questions.sh", "setup-areas-json.sh")


def main():
    overrides = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    edition = sys.argv[2] if len(sys.argv) > 2 else "makerspace"
    overrides.setdefault("Admin email", "owner@example.org")
    with tempfile.TemporaryDirectory() as tmp:
        directory = pathlib.Path(tmp)
        (directory / "scripts").mkdir()
        for name in NAMES:
            source = (ROOT / "scripts" / name).read_text(encoding="utf-8").replace("exec 3</dev/tty", "exec 3<&0")
            (directory / "scripts" / name).write_text(source, encoding="utf-8", newline="\n")
        process = subprocess.Popen(
            ["bash", "-c", "set -euo pipefail; source scripts/setup-questions.sh; ask_setup_questions || exit 0; "
             "setup_areas_json > areas.json"],
            cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={**os.environ, "SPACEWORKS_EDITION": edition}, bufsize=0,
        )
        transcript, buffer, asked = [], b"", []
        while True:
            char = process.stdout.read(1)
            if not char:
                break
            buffer += char
            if buffer.endswith(b"]: "):
                line = buffer.decode().rsplit("\n", 1)[-1]
                label = line.rsplit(" [", 1)[0]
                value = next((value for key, value in overrides.items() if label.startswith(key)), "")
                # A list answers successive repeats of the same prompt (e.g. a retry after bad input).
                answer = (value.pop(0) if value else "") if isinstance(value, list) else value
                asked.append(label)
                transcript.append(f"{line}{answer}")
                process.stdin.write((answer + "\n").encode())
                process.stdin.flush()
                buffer = b""
            elif char == b"\n":
                transcript.append(buffer.decode().rstrip("\n"))
                buffer = b""
        process.wait()
        text = "\n".join(transcript)
        start = text.find("Deployment summary")
        print(f"exit={process.returncode} prompts={len(asked)}")
        print(text[start:] if start >= 0 else text[-3000:])
        areas = directory / "areas.json"
        print("--- areas.json ---")
        print(areas.read_text() if areas.exists() else "(not written)")


if __name__ == "__main__":
    main()
