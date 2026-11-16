"""Fail-closed managers for the two membership tracks (one account per person).

A person may hold a ``community`` row (the Member role) and a ``staff`` row (built-in
staff roles) in the same makerspace. The DEFAULT manager is community-only, so every
reverse relation (``user.makerspace_memberships``, ``makerspace.memberships``) and every
unqualified ``MakerspaceMembership.objects`` read sees community rows and can never
grant staff authority by accident. Staff authority is read explicitly through
``staff_tracks``; ``all_tracks`` exists only for backup, tenant migration, export and
purge (a guard test pins its callers).
"""

from django.db import models

COMMUNITY = "community"
STAFF = "staff"


class CommunityMembershipManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(track=COMMUNITY)


class StaffTrackManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(track=STAFF)


class AllTracksManager(models.Manager):
    """Unfiltered rows; reserved for whole-tenant capture, migration and purge."""
