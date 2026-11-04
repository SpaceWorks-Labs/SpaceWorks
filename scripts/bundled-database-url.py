#!/usr/bin/env python3
"""Derive the bundled runtime URL from one explicit static env file."""

from pathlib import Path
import sys
from urllib.parse import quote


def assignments(path):
    result = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key in result:
            raise RuntimeError("Static environment is malformed or repeats an assignment.")
        result[key] = value
    return result


def main(argv):
    if len(argv) != 2:
        raise SystemExit("usage: bundled-database-url.py <static-env>")
    values = assignments(argv[1])
    if "DATABASE_URL" in values or "SPACEWORKS_DB_POINTER_GENERATION" in values:
        raise RuntimeError("Static environment must not contain database pointer fields.")
    runtime_user = values.get("POSTGRES_APP_USER", "spaceworks_app")
    if runtime_user == values.get("POSTGRES_USER", "makerspace"):
        # Row-level security binds only a role that owns nothing (lane L8, #128 C-25).
        raise RuntimeError("POSTGRES_APP_USER must differ from the table-owning POSTGRES_USER.")
    user = quote(runtime_user, safe="")
    password = quote(values["POSTGRES_APP_PASSWORD"], safe="")
    database = quote(values.get("POSTGRES_DB", "makerspace_manager"), safe="")
    print(f"postgres://{user}:{password}@db:5432/{database}")


if __name__ == "__main__":
    main(sys.argv)
