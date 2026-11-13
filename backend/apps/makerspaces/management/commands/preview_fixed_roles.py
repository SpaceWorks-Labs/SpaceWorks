"""Preview the irreversible fixed-role upgrade against the OLD schema only."""

import json

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction

from apps.makerspaces.migration_support.fixed_roles_projection import build_projection, refusal_message
from apps.makerspaces.migration_support.fixed_roles_snapshot import PRE_SCHEMA_FIELDS, read_snapshot


class Command(BaseCommand):
    help = "Preview fixed-role migration before upgrading (pre-0088 schema; no writes)."
    # The installed code can be newer than the DB. Runtime system checks must not
    # resolve authority or inspect newly introduced tables before this reader runs.
    requires_system_checks = []
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument("--makerspace", type=int, metavar="ID")
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args, **options):
        models = {label: apps.get_model(label) for label in PRE_SCHEMA_FIELDS}
        # One consistent read snapshot even if the current console is still running.
        # Production migration itself requires stopped writers.
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            snapshot = read_snapshot(models, connection, options["makerspace"])
        if options["makerspace"] is not None and not snapshot["makerspaces.Makerspace"]:
            raise CommandError(f"Unknown makerspace {options['makerspace']}.")
        projection = build_projection(snapshot)
        if options["as_json"]:
            # Refusals are the first field, not buried behind membership changes.
            result = {
                "must fix before upgrading": projection["refused_recipient_rules"],
                **{key: value for key, value in projection.items()
                   if key not in {"refused_recipient_rules", "obsolete_role_ids"}},
            }
            self.stdout.write(json.dumps(result, cls=DjangoJSONEncoder, indent=2))
            return
        refused = projection["refused_recipient_rules"]
        if refused:
            self.stdout.write(self.style.ERROR(refusal_message(refused)))
        else:
            self.stdout.write("must fix before upgrading: no obsolete/custom role notification rules.")
        self.stdout.write("Exceptions: E1 = narrowed Space Manager restored; E2 = handover-shaped role becomes Handover.")
        for space in projection["makerspaces"]:
            self.stdout.write(f"\nMakerspace {space['id']}: {space['name']} ({space['slug']})")
            self._memberships(projection, space["id"])
            self._references(projection, space["id"])

    def _memberships(self, projection, space_id):
        for row in projection["memberships"]:
            if row["makerspace_id"] != space_id:
                continue
            before = row["from_role"]
            label = f"{before['name']} ({before['slug']})" if before else f"legacy {row['role']}"
            after = ", ".join(row["to_roles"]) or "legacy unchanged"
            self.stdout.write(f"  Membership {row['id']} (user {row['user_id']}, {row['status']}): {label} -> {after}")
            self.stdout.write(f"    dropped={row['dropped_actions']} gained={row['gained_actions']} exceptions={row['exception_tags']}")
            self.stdout.write(f"    machine scope: {row['machine_scope_outcome']} {json.dumps(row['machine_scope'])}")

    def _references(self, projection, space_id):
        for row in projection["requests"]:
            if row["makerspace_id"] == space_id:
                self.stdout.write(f"  MembershipRequest {row['id']} ({row['state']}): role {row['assigned_role_id']} -> {row['primary_slug']}")
        for row in projection["invitations"]:
            if row["makerspace_id"] == space_id:
                verb = "REVOKED and re-pointed" if row["revoke"] else "re-pointed"
                self.stdout.write(f"  StaffInvitation {row['id']}: {verb} {row['role_id']} -> {row['primary_slug']}; resnapshot={row['resnapshot']}")
        for row in projection["schedules"]:
            if row["makerspace_id"] == space_id:
                self.stdout.write(f"  ReportSchedule {row['id']}: pruned {row['recipient_roles']} -> {row['after_roles']}; deactivate={row['deactivate']}")
