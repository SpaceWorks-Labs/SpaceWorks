"""Redacted probe reports; validate never provisions resources or sends mail."""

from datetime import datetime, timezone
import hashlib
import json

from .database_probe import database_probe
from .errors import SetupError
from .service_probes import email_probe, redis_probe, scanner_probe


def probe(name, function):
    try:
        return {"name": name, **function()}
    except SetupError as exc:
        return {"name": name, **exc.report()}
    except ImportError:
        return {"name": name, "status": "failed", "code": "probe_dependency_unavailable", "action": "Install the checked release's setup dependencies and integrate the named runtime adapter before retrying."}
    except Exception:
        # psycopg/SDK exceptions can contain DSNs, access IDs or signed URLs.
        return {"name": name, "status": "failed", "code": "provider_probe_failed", "action": "Check credentials, TLS, grants and provider capability privately; raw provider errors are deliberately omitted."}


def validate(values, answers, *, final=False):
    checks = [
        probe("database", lambda: database_probe(values, answers, require_identity=final)),
        probe("email", lambda: email_probe(values, answers)),
        probe("tasks", lambda: redis_probe(values, answers)),
        probe("scanner", lambda: scanner_probe(values, answers)),
    ]
    from .secrets import continuity_probe
    checks.append(probe("continuity", lambda: continuity_probe(values, free=answers["profile"] == "free")))
    # Validation is read-only. Conditional PUT/privacy/CORS probes belong to the
    # explicit bootstrap phase, never a validation command.
    from .secret_files import read_config
    checks.append(probe("storage_descriptor", lambda: {"status": "passed" if read_config(values, "STORAGE_CAPABILITIES_FILE") else "failed"}))
    payload = {"version": 1, "checked_at": datetime.now(timezone.utc).isoformat(), "checks": checks}
    payload["status"] = "passed" if all(c["status"] == "passed" for c in checks) else "failed"
    payload["evidence_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload
