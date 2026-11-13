"""Create, re-key and drop analytics logins from the runtime, through the privileged
SECURITY DEFINER functions ``db_sync`` built (the runtime role itself cannot make roles).

Fail safe: every database error becomes ``ProvisioningFailed`` (the console shows "could not
create the login"), and a database without the functions, or a runtime role that may not
call them, is ``not available on this hosting``. Nothing here logs a password, a verifier
or the SQL that carried one.
"""

import base64
import hashlib
import hmac
import logging
import secrets

from django.conf import settings
from django.db import DatabaseError, connections, transaction

from .db_functions import DROP_LOGIN, ENSURE_LOGIN
from .db_names import ADMIN_SCHEMA, PLATFORM_SCHEMA, SPACE_SCHEMA, login_name

logger = logging.getLogger(__name__)
SCRAM_ITERATIONS = 4096


class ProvisioningFailed(Exception):
    pass


def availability(using="default"):
    """(available, reason). Never raises."""
    db = connections[using]
    if db.vendor != "postgresql":
        return False, "not_postgresql"
    try:
        with transaction.atomic(using=using), db.cursor() as cursor:
            cursor.execute(
                "SELECT to_regprocedure(%s) IS NOT NULL AND to_regprocedure(%s) IS NOT NULL", [ENSURE_LOGIN, DROP_LOGIN])
            if not cursor.fetchone()[0]:
                return False, "not_available_on_hosting"
            cursor.execute(
                "SELECT has_schema_privilege(current_user, %s, 'USAGE') "
                "AND has_function_privilege(current_user, %s, 'EXECUTE') "
                "AND has_function_privilege(current_user, %s, 'EXECUTE')", [ADMIN_SCHEMA, ENSURE_LOGIN, DROP_LOGIN])
            if not cursor.fetchone()[0]:
                return False, "not_available_on_hosting"
    except DatabaseError:
        logger.warning("analytics_availability_check_failed")
        return False, "check_failed"
    return True, ""


def new_password():
    return secrets.token_urlsafe(24)


def scram_verifier(password, *, salt=None, iterations=SCRAM_ITERATIONS):
    """The SCRAM-SHA-256 verifier PostgreSQL stores (RFC 5802/7677), computed here so the
    clear password never travels to the server."""
    salt = salt if salt is not None else secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    b64 = lambda raw: base64.b64encode(raw).decode("ascii")  # noqa: E731
    return f"SCRAM-SHA-256${iterations}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}"


def _database_name(cursor):
    cursor.execute("SELECT current_database()")
    return cursor.fetchone()[0]


def _call(statement, params, using):
    try:
        with transaction.atomic(using=using), connections[using].cursor() as cursor:
            cursor.execute(statement, params)
    except DatabaseError as exc:
        # The class only: the statement carried a password verifier.
        logger.warning("analytics_provisioning_failed", extra={"error": exc.__class__.__name__})
        raise ProvisioningFailed() from None


def generate_login_name(makerspace_id, using="default"):
    with connections[using].cursor() as cursor:
        return login_name(_database_name(cursor), makerspace_id, secrets.token_hex(3))


def ensure_login(role, password, makerspace_id, using="default"):
    """Create the login, or reset an existing one's password (also recreates a login a
    database restore left without its role)."""
    _call(f"SELECT {ADMIN_SCHEMA}.ensure_login(%s, %s, %s)",
          [role, scram_verifier(password), makerspace_id], using)


def drop_login(role, using="default"):
    _call(f"SELECT {ADMIN_SCHEMA}.drop_login(%s)", [role], using)


def drop_login_quietly(role, using="default"):
    """For deletes and purges: never raises; a leftover login is reported, not fatal."""
    if not role:
        return
    try:
        drop_login(role, using)
    except ProvisioningFailed:
        logger.warning("analytics_login_left_behind")


def login_exists(role, using="default"):
    if not role:
        return False
    try:
        with connections[using].cursor() as cursor:
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", [role])
            return bool(cursor.fetchone()[0])
    except DatabaseError:
        return False


def connection_details(*, platform):
    """What Metabase needs besides the role and password. The host is the address the app
    uses; a Metabase on another network may need the database's public address instead."""
    database = settings.DATABASES["default"]
    return {
        "host": database.get("HOST") or "localhost",
        "port": int(database.get("PORT") or 5432),
        "database": database.get("NAME") or "",
        "schema": PLATFORM_SCHEMA if platform else SPACE_SCHEMA,
    }
