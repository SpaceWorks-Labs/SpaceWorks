#!/usr/bin/env python3
"""Consume private Compose JSON and emit only its non-secret project identity."""
import json
import re
import sys


def main():
    name = json.load(sys.stdin).get("name", "")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
        raise ValueError("Invalid project identity.")
    print(name)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, AttributeError, TypeError):
        sys.exit("Cannot prove the Compose project identity; private configuration was not printed.")
