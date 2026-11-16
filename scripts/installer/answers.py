#!/usr/bin/env python3
"""Read version 1 noninteractive JSON; output data as NUL frames, never shell code.

Schema: {"schema_version": 1, "confirmed": true, "answers": {"ORG_NAME": "...",
"ADMINEMAIL": "...", "AREA_ENABLE_inventory": "Y", ...}}. Other keys are the
questionnaire's variable names. Unspecified optional questions keep their defaults;
unused/unknown answers are rejected by the questionnaire before installation.
"""
import json
import os
from pathlib import Path
import re
import stat
import sys


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate answer field.")
        result[key] = value
    return result


def main():
    path = Path(sys.argv[1])
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 100_000:
        raise ValueError("Answers must be a bounded regular JSON file.")
    from private_files import check_private
    check_private(path)
    document = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)
    if (set(document) != {"schema_version", "confirmed", "answers"}
            or type(document["schema_version"]) is not int or document["schema_version"] != 1
            or document["confirmed"] is not True or not isinstance(document["answers"], dict)):
        raise ValueError("Expected version 1 answers with explicit confirmation.")
    answers = document["answers"]
    for required in ("ORG_NAME", "ADMINEMAIL"):
        if not answers.get(required):
            raise ValueError("Required organization/admin answer is missing.")
    for key, value in answers.items():
        if (not re.fullmatch(r"[A-Z][A-Za-z0-9_]{0,100}", key) or not isinstance(value, str)
                or len(value) > 4096 or any(ord(char) < 32 or ord(char) == 127 for char in value)):
            raise ValueError("Invalid answer name or value.")
    # Validate all entries before emitting any data.
    for key, value in answers.items():
        sys.stdout.buffer.write(key.encode() + b"\0" + value.encode() + b"\0")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, RecursionError):
        sys.exit("Invalid private answers file; use schema_version 1 and supply required deployment fields.")
