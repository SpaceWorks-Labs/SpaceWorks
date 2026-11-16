"""Two operator-supplied scratch DBs; qualification never destroys either DB."""

import json
import os
from pathlib import Path
import stat
import uuid

from .connection import DatabaseConfigurationError, connect_database, database_spec


class ScratchUnavailable(DatabaseConfigurationError):
    code = "portable_dump_scratch_unavailable"


def scratch_specs(filename, *, environ=None):
    """Version 1 file: {version: 1, databases: [{url, connection_mode}, ...]}."""
    try:
        path = Path(filename)
        if path.is_symlink():
            raise ValueError
        with path.open("rb") as stream:
            facts = os.fstat(stream.fileno())
            if not stat.S_ISREG(facts.st_mode) or facts.st_mode & 0o077 or facts.st_size > 16384:
                raise ValueError
            if hasattr(os, "geteuid") and facts.st_uid not in {0, os.geteuid()}:
                raise ValueError
            document = json.load(stream)
        if set(document) != {"version", "databases"} or document["version"] != 1 or len(document["databases"]) != 2:
            raise ValueError
        specs = []
        for item in document["databases"]:
            if set(item) != {"url", "connection_mode"}:
                raise ValueError
            specs.append(database_spec(item["url"], mode=item["connection_mode"], managed=True, environ=environ))
        if specs[0].parameters == specs[1].parameters:
            raise ValueError
        return tuple(specs)
    except Exception:
        raise ScratchUnavailable("Provide two isolated scratch databases in a private version-1 file.") from None


def qualify_scratch(specs, *, application_uuid, runtime_roles):
    """Read a job-admin-provisioned identity marker before any restore writes.

    I's allocator creates public.spaceworks_scratch_identity(id=1,
    database_uuid UUID, non_routable BOOLEAN), owned by the scratch SQL principal.
    Runtime credentials must have no CONNECT privilege to these databases.
    """
    identities = set()
    endpoints = set()
    if not runtime_roles:
        raise ScratchUnavailable("Scratch qualification requires the deployment runtime principal inventory.")
    for spec in specs:
        try:
            with connect_database(spec) as database, database.cursor() as cursor:
                cursor.execute("SELECT current_database(), (SELECT oid FROM pg_database WHERE datname=current_database()), NOT pg_is_in_recovery(), (SELECT datdba=(SELECT oid FROM pg_roles WHERE rolname=current_user) FROM pg_database WHERE datname=current_database())")
                name, oid, primary, owner = cursor.fetchone()
                if not primary or not owner:
                    raise ValueError
                for role in runtime_roles:
                    cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=%s)", [role])
                    if cursor.fetchone()[0]:
                        cursor.execute("SELECT has_database_privilege(%s, current_database(), 'CONNECT')", [role])
                        if cursor.fetchone()[0]:
                            raise ValueError
                cursor.execute("SELECT database_uuid::text, non_routable FROM public.spaceworks_scratch_identity WHERE id=1")
                row = cursor.fetchone()
                if row is None or not row[1]:
                    raise ValueError
                identity = str(uuid.UUID(row[0]))
                endpoint = (spec.parameters["host"], int(spec.parameters.get("port", 5432)), name)
                if identity == str(application_uuid) or identity in identities or endpoint in endpoints:
                    raise ValueError
                cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind IN ('r', 'p') AND n.nspname='public' AND c.relname <> 'spaceworks_scratch_identity')")
                if cursor.fetchone()[0]:
                    raise ValueError
                identities.add(identity)
                endpoints.add(endpoint)
        except Exception:
            raise ScratchUnavailable("Scratch identity, ownership, isolation or emptiness could not be proven.") from None
    if len(identities) != 2:
        raise ScratchUnavailable("Exactly two isolated scratch databases are required.")
    return {"scratch_databases": 2, "ownership": "operator", "automatic_delete": False}
