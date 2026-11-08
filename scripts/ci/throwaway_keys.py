#!/usr/bin/env python3
"""Print fresh, throwaway keys as KEY=value lines for the Checks workflow.

The backend's system checks need a SECRET_KEY and well-formed Fernet keys
(PII_MASTER_KEY is mandatory because finance fields are always encrypted). These are
generated per run and never persisted; nothing encrypted with them outlives the job.

CI:     python scripts/ci/throwaway_keys.py >> "$GITHUB_ENV"
Local:  eval "$(python scripts/ci/throwaway_keys.py | sed 's/^/export /')"
"""
import secrets

from cryptography.fernet import Fernet

print(f"SECRET_KEY={secrets.token_urlsafe(50)}")
for name in ("API_CLIENT_ENC_KEY", "AUDIT_MAC_MASTER_KEY", "PII_MASTER_KEY"):
    print(f"{name}={Fernet.generate_key().decode()}")
