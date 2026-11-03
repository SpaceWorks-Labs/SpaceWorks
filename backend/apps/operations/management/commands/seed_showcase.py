"""Seed one rich, fictional demo makerspace ("Tinkerspace") for screenshots.

Every row is written through the service, serializer or workflow that owns it, so the
showcase carries the same audit trail, evidence and invariants as real use: request
transitions go through `hardware_requests.workflow`, quantities through
`inventory.availability`, machine jobs through the machine service workflow and money
through the payments ledger. Nothing writes a status or quantity field directly.

The shared password is never printed. Pass `--password`, or let the command generate
one and write it ONLY to `--credentials-file`.
"""
import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.makerspaces import lifecycle
from apps.makerspaces.models import Makerspace

from . import _showcase_data as data
from ._showcase_community import (
    membership_plan, publish_public_page, seed_bookings, seed_notices, settle_some_dues,
)
from ._showcase_events import seed_events
from ._showcase_finance import seed_finance
from ._showcase_hackathon import seed_hackathon
from ._showcase_inventory import seed_inventory
from ._showcase_machines import seed_machines
from ._showcase_membership_l4 import seed_membership_lifecycle
from ._showcase_pricing import seed_pricing
from ._showcase_l12 import seed_l12
from ._showcase_l6 import seed_ticketing
from ._showcase_people import create_members, create_space, create_staff, member_account, restrict
from ._showcase_requests import RequestSeeder


class Command(BaseCommand):
    help = "Seed the fictional Tinkerspace showcase through the real services."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=None,
                            help="Password for every showcase account. Never printed.")
        parser.add_argument("--credentials-file", default=None,
                            help="Where to write a generated password (required without --password).")
        parser.add_argument("--reset", action="store_true",
                            help="Archive and purge an existing showcase space, then rebuild it.")
        parser.add_argument("--allow-production-demo", action="store_true",
                            help="Explicitly allow fictional demo data in a production database.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_production_demo"]:
            raise CommandError(
                "seed_showcase requires DEBUG=True or the explicit --allow-production-demo flag."
            )
        password, credentials = options["password"], options["credentials_file"]
        if not password and not credentials:
            raise CommandError("Pass --password, or --credentials-file to receive a generated one.")
        existing = Makerspace.objects.filter(slug=data.SLUG).first()
        if existing is not None and not options["reset"]:
            raise CommandError(f"{data.NAME} already exists; pass --reset to rebuild it.")
        if not password:
            password = secrets.token_urlsafe(18)
            self._write_credentials(Path(credentials), password)
        root = member_account(*data.SUPERADMIN, password, kind="platform",
                              role=User.Role.SUPERADMIN, is_staff=True)
        if existing is not None:
            lifecycle.purge(lifecycle.archive(existing, root), root)
        space = self._build(root, password)
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {space.name} (/{space.slug}). Superadmin: {root.username}. "
            f"Staff: {', '.join(name for name, *_ in data.STAFF)}. "
            f"Members: {len(data.MEMBERS)} active plus {data.RESTRICTED_MEMBER[0]} (restricted)."
        ))
        if credentials:
            self.stdout.write(f"Credentials written to {credentials}.")

    def _build(self, root, password):
        space = create_space(root)
        staff = create_staff(space, root, password)
        plan = membership_plan(space, staff.manager)
        members = create_members(space, root, staff.manager, plan, password)
        seed_membership_lifecycle(space, staff.manager, members)
        stock = seed_inventory(space, staff.manager, staff.inventory)
        RequestSeeder(space, staff, members, stock).run()
        seed_machines(space, staff.manager, staff.machines, members)
        settle_some_dues(space, staff.manager, members)
        seed_finance(space, staff.manager)
        seed_pricing(space, staff.manager, plan)
        seed_bookings(space, staff.manager, members)
        seed_l12(space, staff.manager, staff.inventory, staff.machines, members)
        seed_notices(space, staff.manager)
        seed_hackathon(space, staff.manager, members)
        seed_events(space, staff.manager)
        seed_ticketing(space, staff.manager, next(iter(members.values())))
        publish_public_page(space, staff.manager)
        restrict(root, members[data.RESTRICTED_MEMBER[0]],
                 "Two multimeters not returned after the March repair cafe.")
        return space

    def _write_credentials(self, path, password):
        path.parent.mkdir(parents=True, exist_ok=True)
        accounts = [data.SUPERADMIN[0], *(name for name, *_ in data.STAFF),
                    *(name for name, _ in data.MEMBERS), data.RESTRICTED_MEMBER[0]]
        path.write_text(
            f"{data.NAME} showcase accounts (fictional). Password for every account:\n"
            f"{password}\n\nAccounts:\n" + "\n".join(accounts) + "\n",
            encoding="utf-8",
        )
