#!/usr/bin/env python3
"""Validate existing local/HMAC key encoding without Django or secret argv."""
import base64
import os
import sys


def main():
    values = {}
    for name in ("PII_MASTER_KEY", "PII_MASTER_KEY_PREVIOUS", "PII_SEARCH_HASH_KEY"):
        value = os.environ.get(name, "")
        if not value:
            continue
        raw = value.encode("ascii")
        decoded = base64.b64decode(raw + b"=" * (-len(raw) % 4), altchars=b"-_", validate=True)
        if len(decoded) != 32:
            raise ValueError("Invalid key length.")
        values[name] = decoded
    if values.get("PII_MASTER_KEY") and values.get("PII_MASTER_KEY") == values.get("PII_SEARCH_HASH_KEY"):
        raise ValueError("Master and search keys must be independent.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, UnicodeError):
        sys.exit("Existing encryption material is invalid; recover its original 256-bit key instead of replacing it.")
