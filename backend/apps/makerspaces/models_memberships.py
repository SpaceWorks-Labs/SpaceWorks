from django.utils.translation import gettext, gettext_noop
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.makerspaces.membership_managers import (
    COMMUNITY, STAFF, AllTracksManager, CommunityMembershipManager, StaffTrackManager,
)
from apps.makerspaces.models_makerspace import Makerspace
from apps.makerspaces.provenance import validate_actor_snapshot


class MakerspaceMembership(models.Model):
    # Role is per-makerspace and per TRACK: one person may hold a community row (Member)
    # and a staff row (built-in staff roles) in the same makerspace. Global User.role
    # stays for superadmin. Enforcement is centralized in the RBAC layer; the default
    # manager is community-only so staff authority is never read by accident.
    class Track(models.TextChoices):
        COMMUNITY = COMMUNITY, "Community"
        STAFF = STAFF, "Staff"

    class Role(models.TextChoices):
        SPACE_MANAGER = "space_manager", gettext_noop("Space Manager")
        INVENTORY_MANAGER = "inventory_manager", gettext_noop("Inventory Manager")
        PRINT_MANAGER = "print_manager", gettext_noop("Print Manager")
        # Makerspace-wide machine authority: manages assigned machines end-to-end
        # (the machine + usage/cycle + warranty + maintenance). Action set is exactly
        # {MANAGE_MACHINES}; every machine sub-feature already gates on machine access,
        # so no new RBAC action is needed. Delegable by a Space Manager (Part I).
        MACHINE_MANAGER = "machine_manager", gettext_noop("Machine Manager")
        EVENT_MANAGER = "event_manager", gettext_noop("Event Manager")
        BOOKING_MANAGER = "booking_manager", gettext_noop("Booking Manager")
        HANDOVER = "handover", gettext_noop("Handover")
        TECHNICIAN = "technician", gettext_noop("Technician")
        SHOP_MANAGER = "shop_manager", gettext_noop("Shop Manager")
        FUNDRAISING = "fundraising", gettext_noop("Fundraising")  # decision 242(m)
        CUSTOM = "custom", gettext_noop("Custom")

    objects = CommunityMembershipManager()
    staff_tracks = StaffTrackManager()
    all_tracks = AllTracksManager()

    @classmethod
    def track_manager(cls, track):
        """The fail-closed manager for one known track (never ``all_tracks``)."""
        return cls.staff_tracks if track == cls.Track.STAFF else cls.objects

    @classmethod
    def both_tracks(cls):
        """Community OR staff rows, chosen on purpose: a person's whole relation to a
        space (notification recipients, account scope). Never for authority."""
        return cls.objects.all() | cls.staff_tracks.all()

    makerspace = models.ForeignKey(
        Makerspace,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    # Immutable once written (DB trigger): the membership-FK track triggers depend on it.
    track = models.CharField(max_length=16, choices=Track.choices, default=Track.COMMUNITY)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="makerspace_memberships",
        limit_choices_to={"is_active": True},
    )
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.SPACE_MANAGER)
    assigned_role = models.ForeignKey(
        "makerspaces.MakerspaceRole",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    # Per-makerspace opt-in for staff lifecycle email notifications. Default True keeps
    # existing behavior (every relevant manager is notified); the space manager can turn
    # an individual manager off in Settings without removing their access.
    receives_notifications = models.BooleanField(default=True)
    can_refer = models.BooleanField(default=True)
    can_verify = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_memberships",
    )
    verified_actor_snapshot = models.JSONField(
        null=True, blank=True, validators=[validate_actor_snapshot]
    )
    status = models.CharField(
        max_length=16,
        choices=(("active", "Active"), ("revoked", "Revoked")),
        default="active",
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="activated_makerspace_memberships",
    )
    activated_actor_snapshot = models.JSONField(
        null=True, blank=True, validators=[validate_actor_snapshot]
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="revoked_makerspace_memberships",
    )
    revoked_actor_snapshot = models.JSONField(
        null=True, blank=True, validators=[validate_actor_snapshot]
    )
    revocation_reason = models.TextField(blank=True)
    renewal_cancelled_at = models.DateTimeField(null=True, blank=True)
    waiver_accepted_at = models.DateTimeField(null=True, blank=True)
    waiver_version_accepted = models.CharField(max_length=64, null=True, blank=True)
    accepted_waiver = models.ForeignKey(
        "makerspaces.MakerspaceWaiver", null=True, blank=True, on_delete=models.PROTECT,
        related_name="accepted_by_memberships",
    )
    witnessed_waiver = models.ForeignKey(
        "makerspaces.MakerspaceWaiver", null=True, blank=True, on_delete=models.PROTECT,
        related_name="witnessed_by_memberships",
    )
    witnessed_waiver_version = models.CharField(max_length=64, null=True, blank=True)
    witnessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="witnessed_waiver_acceptances",
    )
    witnessed_actor_snapshot = models.JSONField(null=True, blank=True)
    witnessed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Gapless per-space member number, assigned at first activation and kept for life --
    # through card reissue, revocation and rejoining (X12). Printed with the space's
    # optional prefix (`MakerspaceMembershipSettings.member_number_prefix`).
    member_number = models.PositiveIntegerField(null=True, blank=True)
    # How the person first became a member here (X13): join / manual / import.
    source = models.CharField(max_length=16, blank=True, default="",
                              choices=[("join", "Joined"), ("manual", "Added by staff"), ("import", "Imported")])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["makerspace", "user", "track"],
                name="uniq_makerspace_user_track",
            ),
            models.UniqueConstraint(
                fields=["makerspace", "member_number"], condition=Q(member_number__isnull=False),
                name="uniq_makerspace_member_number",
            ),
            models.CheckConstraint(
                condition=(
                    Q(waiver_accepted_at__isnull=True, waiver_version_accepted__isnull=True,
                      accepted_waiver__isnull=True)
                    | Q(waiver_accepted_at__isnull=False, waiver_version_accepted__isnull=False,
                        accepted_waiver__isnull=False)
                ),
                name="membership_waiver_acceptance_all_or_none",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        witnessed_waiver__isnull=True,
                        witnessed_waiver_version__isnull=True,
                        witnessed_by__isnull=True,
                        witnessed_actor_snapshot__isnull=True,
                        witnessed_at__isnull=True,
                    )
                    | Q(
                        witnessed_waiver__isnull=False,
                        witnessed_waiver_version__isnull=False,
                        witnessed_at__isnull=False,
                    )
                    & (
                        Q(witnessed_by__isnull=False)
                        | Q(witnessed_actor_snapshot__isnull=False)
                    )
                ),
                name="membership_witnessed_waiver_all_or_none",
            ),
        ]

    def clean(self):
        # Block assigning a membership to a deactivated account (covers the User-side
        # inline where user is the parent and limit_choices_to does not apply).
        if self.user_id and not self.user.is_active:
            raise ValidationError(gettext("Cannot assign a makerspace to an inactive user."))
        # An assigned custom role must belong to the SAME makerspace as this
        # membership. Defense-in-depth: the RBAC reader also fails closed on a
        # tenant mismatch, and the role-assignment service rejects it at write.
        if (
            self.assigned_role_id
            and self.makerspace_id
            and self.assigned_role.makerspace_id != self.makerspace_id
        ):
            raise ValidationError(
                {"assigned_role": gettext("Role must belong to the same makerspace.")}
            )
        if (
            self.accepted_waiver_id and self.makerspace_id
            and self.accepted_waiver.makerspace_id != self.makerspace_id
        ):
            raise ValidationError({"accepted_waiver": gettext("Waiver must belong to the same makerspace.")})
        if (
            self.witnessed_waiver_id and self.makerspace_id
            and self.witnessed_waiver.makerspace_id != self.makerspace_id
        ):
            raise ValidationError(
                {"witnessed_waiver": gettext("Waiver must belong to the same makerspace.")}
            )

    def __str__(self):
        return f"{self.user} @ {self.makerspace.slug} ({self.track}: {self.role})"
