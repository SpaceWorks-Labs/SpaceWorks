"""The account-unification plan: what converting every staff account will do.

Shared by ``manage.py account_unification_report`` and the unification migrations, so
the ``plan_sha256`` an operator acknowledges is exactly the plan the migration runs.
It reads ONLY columns that exist before the unified-accounts schema (raw SQL, no
models), so the report works on an unmigrated database and inside a migration. A live
staff account always has a ``staff_makerspace``; inert shells never do, so after the
conversion the plan is empty and ``plan_sha256`` is the digest of no decisions. Later
extensions (U-C's merge progress) must not change what the digest covers.

Hold rule (Q14): a person's existing address always stays with that person. A staff
account's email, phone or Telegram id is moved to an encrypted hold when it equals a
person's, or another converting staff account's (no staff account is preferred).
"""

import hashlib
import json
from collections import Counter, defaultdict

PLAN_VERSION = 1
HELD_FIELDS = ("email", "phone_e164", "telegram_user_id")


def _rows(cursor, sql, params=()):
    cursor.execute(sql, params)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _identity(row, field):
    value = (row[field] or "").strip()
    return value.lower() if field == "email" else value


def _staff_roles(cursor, staff_ids):
    if not staff_ids:
        return {}
    memberships = _rows(cursor, """
        SELECT m.id, m.user_id, m.makerspace_id, m.status, r.slug
        FROM makerspaces_makerspacemembership m
        LEFT JOIN makerspaces_makerspacerole r ON r.id = m.assigned_role_id
        WHERE m.user_id = ANY(%s) ORDER BY m.id""", [list(staff_ids)])
    links = defaultdict(list)
    for link in _rows(cursor, """
            SELECT l.membership_id, r.slug FROM makerspaces_membershipadditionalrole l
            JOIN makerspaces_makerspacerole r ON r.id = l.role_id
            WHERE l.membership_id = ANY(%s) ORDER BY r.slug""",
            [[row["id"] for row in memberships]]):
        links[link["membership_id"]].append(link["slug"])
    roles = defaultdict(list)
    for row in memberships:
        roles[row["user_id"]].append({
            "makerspace_id": row["makerspace_id"], "status": row["status"],
            "roles": [row["slug"] or "unassigned", *links[row["id"]]],
        })
    return roles


def _holds(staff, persons):
    taken = {field: {_identity(row, field) for row in persons} - {""} for field in HELD_FIELDS}
    counts = {field: Counter(_identity(row, field) for row in staff) for field in HELD_FIELDS}
    holds = {}
    for row in staff:
        holds[row["id"]] = [
            field for field in HELD_FIELDS
            if (value := _identity(row, field)) and (value in taken[field] or counts[field][value] > 1)
        ]
    return holds


def build_plan(connection):
    """Return the full plan dict, including its ``plan_sha256``."""
    with connection.cursor() as cursor:
        staff = _rows(cursor, """
            SELECT u.id, u.username, u.email, u.phone_e164, u.telegram_user_id,
                   u.staff_makerspace_id, u.is_active, s.slug AS makerspace_slug,
                   (mfa.enabled_at IS NOT NULL) AS mfa_enabled
            FROM accounts_user u
            LEFT JOIN makerspaces_makerspace s ON s.id = u.staff_makerspace_id
            LEFT JOIN accounts_usermfa mfa ON mfa.user_id = u.id
            WHERE u.account_kind = 'staff' AND u.retired_at IS NULL
              AND u.staff_makerspace_id IS NOT NULL ORDER BY u.id""")
        persons = _rows(cursor, """
            SELECT id, email, phone_e164, telegram_user_id FROM accounts_user
            WHERE account_kind = 'member' ORDER BY id""")
        roles = _staff_roles(cursor, [row["id"] for row in staff])
    holds = _holds(staff, persons)
    by_email = defaultdict(list)
    for person in persons:
        if email := _identity(person, "email"):
            by_email[email].append(person["id"])
    accounts = [{
        "id": row["id"], "username": row["username"],
        "makerspace_id": row["staff_makerspace_id"], "makerspace_slug": row["makerspace_slug"],
        "is_active": row["is_active"], "outcome": "converted",
        "roles": roles.get(row["id"], []), "holds": holds[row["id"]],
        "mfa_enabled": bool(row["mfa_enabled"]),
    } for row in staff]
    pairs = [{"staff_id": row["id"], "person_id": person_id, "match": "email"}
             for row in staff for person_id in by_email.get(_identity(row, "email"), [])]
    plan = {
        "version": PLAN_VERSION, "staff_accounts": accounts,
        "last_manager_checks": _last_manager_checks(accounts),
        "candidate_pairs": pairs,
    }
    plan["plan_sha256"] = plan_sha256(accounts)
    return plan


def _last_manager_checks(accounts):
    managers = Counter()
    spaces = set()
    for account in accounts:
        for row in account["roles"]:
            spaces.add(row["makerspace_id"])
            if account["is_active"] and row["status"] == "active" and "space_manager" in row["roles"]:
                managers[row["makerspace_id"]] += 1
    return [{"makerspace_id": space, "active_space_managers": managers[space],
             "ok": managers[space] > 0} for space in sorted(spaces)]


def plan_sha256(accounts):
    """Digest of the decisions only: who converts, with which roles and holds."""
    decisions = [{key: account[key] for key in ("id", "username", "makerspace_id", "roles", "holds")}
                 for account in accounts]
    canonical = json.dumps({"version": PLAN_VERSION, "accounts": decisions},
                           sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def assert_acknowledged(connection, acknowledgement):
    """Refuse to touch live staff accounts unless the operator acked this exact plan."""
    plan = build_plan(connection)
    if plan["staff_accounts"] and (acknowledgement or "").strip() != plan["plan_sha256"]:
        raise RuntimeError(
            "Account unification would convert "
            f"{len(plan['staff_accounts'])} staff account(s). Run "
            "`manage.py account_unification_report`, review it, then set "
            "ACCOUNT_UNIFICATION_ACK to the plan_sha256 it prints and migrate again."
        )
    return plan
