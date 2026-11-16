"""Host command: who still needs to set up two-step sign-in before staff MFA bites (#62, #66).

Lists every person with elevated authority and no factor, per space, with the end of
their 3-day grace (#128 C-1) and who can reset them if they lose a factor later (the
superadmin for Space Managers and for people with authority in more than one space;
otherwise also that space's Space Manager). Read-only: nothing is revoked or started.
"""

from django.core.management.base import BaseCommand

from apps.accounts import mfa_policy
from apps.accounts.models import User
from apps.accounts.models_mfa_grace import StaffMfaGrace
from apps.accounts.staff_identity import person_q


class Command(BaseCommand):
    help = "List elevated accounts with no second factor, per space, and their reset path."

    def handle(self, *args, **options):
        from apps.accounts import rbac
        from apps.makerspaces.models import MakerspaceMembership
        graces = dict(StaffMfaGrace.objects.values_list("user_id", "ends_at"))
        rows = []
        for person in User.objects.filter(person_q(), is_active=True).order_by("username").iterator():
            if not mfa_policy.required(person) or mfa_policy.staff_factor_enrolled(person):
                continue
            spaces = list(MakerspaceMembership.staff_tracks.filter(user=person, status="active")
                          .select_related("makerspace").order_by("makerspace__slug"))
            ends = graces.get(person.pk)
            grace = ends.isoformat() if ends else "starts at next sign-in"
            for row in spaces or [None]:
                slug = row.makerspace.slug if row else "(organization or resource grant)"
                manager = row is not None and rbac.is_space_manager_identity(person, row.makerspace_id)
                path = ("superadmin" if manager or len(spaces) != 1 or row is None
                        or rbac.has_any_org_authority(person) else "superadmin or the space's Space Manager")
                rows.append(f"{slug}\t{person.username}\tgrace ends: {grace}\treset: {path}")
        for line in rows:
            self.stdout.write(line)
        self.stdout.write(f"{len(rows)} staff row(s) without a second factor.")
