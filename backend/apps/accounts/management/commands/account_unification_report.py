"""Dry-run report of the one-account-per-person conversion; it never changes data.

Run it BEFORE ``migrate``: it reads only pre-unification columns. The migration refuses
to convert live staff accounts until ``ACCOUNT_UNIFICATION_ACK`` equals the
``plan_sha256`` printed here, so every deployment reviews its own plan first. Open PII
windows and security locks are listed for information only; they are not in the digest.
"""

import json

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections

from apps.accounts.unification_plan import build_plan
from apps.accounts.unification_report_context import security_context


class Command(BaseCommand):
    help = "Report how account unification will convert every staff account (dry run)."

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument("--database", default=DEFAULT_DB_ALIAS)

    def handle(self, *args, **options):
        connection = connections[options["database"]]
        plan = build_plan(connection)
        plan["informational"] = security_context(connection)
        if options["format"] == "json":
            self.stdout.write(json.dumps(plan, indent=2, sort_keys=True, default=str))
            return
        self._text(plan)

    def _text(self, plan):
        accounts = plan["staff_accounts"]
        write = self.stdout.write
        write(f"Staff accounts to convert: {len(accounts)}")
        for account in accounts:
            holds = ", ".join(account["holds"]) or "none"
            write(f"- #{account['id']} {account['username']} "
                  f"({account['makerspace_slug'] or 'no space'}): {account['outcome']}; "
                  f"holds: {holds}; MFA: {'enrolled' if account['mfa_enabled'] else 'not enrolled'}"
                  f"{'' if account['is_active'] else '; inactive'}")
            for row in account["roles"]:
                write(f"    space {row['makerspace_id']} [{row['status']}]: {', '.join(row['roles'])}")
        for check in plan["last_manager_checks"]:
            if not check["ok"]:
                write(f"WARNING: space {check['makerspace_id']} has no active Space Manager.")
        if plan["candidate_pairs"]:
            write(f"Candidate merge pairs (informational; nothing merges automatically): "
                  f"{len(plan['candidate_pairs'])}")
            for pair in plan["candidate_pairs"]:
                write(f"    staff #{pair['staff_id']} and person #{pair['person_id']} share an email")
        self._security(plan["informational"])
        write("Every converted account signs in with its username; held addresses stop "
              "working for sign-in and reset until the person verifies or merges.")
        write(f"plan_sha256: {plan['plan_sha256']}")

    def _security(self, context):
        write = self.stdout.write
        for row in context["open_pii_windows"]:
            where = f"space {row['makerspace_id']}" if row["makerspace_id"] else "per-person reveals"
            write(f"Open PII windows ({where}): {row['open']} (informational; unchanged)")
        for row in context["security_locks"]:
            write(f"Security locks in space {row['makerspace_id']}: {', '.join(row['keys'])} "
                  "(informational; unchanged)")
