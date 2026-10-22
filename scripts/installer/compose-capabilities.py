#!/usr/bin/env python3
"""Verify semantics of the exact Compose merge features used by our overlays."""
import json
import sys


def main():
    config = json.load(sys.stdin)
    service = config["services"]["probe"]
    if service.get("ports") or service.get("environment") != {"ONLY": "replacement"}:
        raise ValueError("Compose does not implement !reset and !override correctly.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError):
        sys.exit("Compose feature probe failed; install a current Docker Compose plugin.")
