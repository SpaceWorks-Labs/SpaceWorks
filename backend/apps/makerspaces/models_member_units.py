"""Release 0.12.0 (parity O-B1): member units inside one makerspace.

A *unit* is a district, chapter or branch of a club or association whose members all live in ONE
makerspace (the organisation's home space). Units are a tree of at most four named levels with a
materialised `path`, so "this unit and everything under it" is one `startswith` filter.

Tables, all tenant data that travels with the space:

* `MemberUnitSettings` -- the space's level names ("District", "Chapter", ...), at most four.
* `MemberUnit` -- one node. Archived, never deleted, once anything points at it.
* `MembershipUnit` -- the unit a community membership belongs to (one per membership).
* `StaffUnitScope` -- narrows one STAFF membership's local authority to a unit's subtree.
* `PlanUnit` -- limits a plan to units (the subtree inherits).
* `MembershipRequestUnit` -- the unit an applicant picked on the join form; copied to the
  membership when it activates.
* `ImportedMemberUnit` -- the unit of an imported row and, in "verify" mode, its review state.

Every side table carries a denormalised `makerspace` so tenant scoping is one predicate.
"""
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_noop

MAX_LEVELS = 4
CODE_VALIDATOR = RegexValidator(r"^[A-Z0-9]{1,6}$", "Use 1 to 6 capital letters or digits.")


class MemberUnitSettings(models.Model):
    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE,
                                      related_name="member_unit_settings")
    #: Names of levels 0..3 in order, e.g. ["District", "Chapter"]. Fewer than four is normal.
    level_names = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class MemberUnit(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="member_units")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80)
    code = models.CharField(max_length=6, validators=[CODE_VALIDATOR])
    level = models.PositiveSmallIntegerField(default=0)
    #: Materialised path of CODES, "/NORTH/KOCHI/": the unit and every ancestor, starting and ending with "/".
    #: Codes are unique per space and cannot change once a unit has children or members, so a path never goes
    #: stale and travels unchanged in a tenant dump (an id path would need remapping).
    path = models.CharField(max_length=64, default="", blank=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    #: Offline payment instructions (UPI id, bank details). The nearest ancestor that has any is shown.
    payment_instructions = models.TextField(blank=True, default="")
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["level", "sort_order", "name", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "code"], name="uniq_member_unit_code"),
            models.UniqueConstraint(fields=["makerspace", "slug"], name="uniq_member_unit_slug"),
            models.CheckConstraint(condition=Q(level__lte=MAX_LEVELS - 1), name="member_unit_level_range"),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class MembershipUnit(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="membership_unit_rows")
    membership = models.OneToOneField("makerspaces.MakerspaceMembership", on_delete=models.CASCADE,
                                      related_name="unit_assignment")
    unit = models.ForeignKey(MemberUnit, on_delete=models.PROTECT, related_name="member_rows")
    assigned_at = models.DateTimeField(auto_now=True)


class StaffUnitScope(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="staff_unit_scope_rows")
    #: A STAFF-track membership (the row that holds the staff role), not the person's community row.
    membership = models.OneToOneField("makerspaces.MakerspaceMembership", on_delete=models.CASCADE,
                                      related_name="unit_scope")
    unit = models.ForeignKey(MemberUnit, on_delete=models.PROTECT, related_name="staff_scopes")
    updated_at = models.DateTimeField(auto_now=True)


class PlanUnit(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="plan_unit_rows")
    plan = models.ForeignKey("makerspaces.MembershipPlan", on_delete=models.CASCADE, related_name="unit_links")
    unit = models.ForeignKey(MemberUnit, on_delete=models.PROTECT, related_name="plan_links")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["plan", "unit"], name="uniq_plan_unit")]


class MembershipRequestUnit(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="request_unit_rows")
    request = models.OneToOneField("makerspaces.MembershipRequest", on_delete=models.CASCADE,
                                   related_name="unit_choice")
    unit = models.ForeignKey(MemberUnit, on_delete=models.PROTECT, related_name="request_rows")


class ImportedMemberUnit(models.Model):
    class Review(models.TextChoices):
        NOT_REQUIRED = "not_required", gettext_noop("Not required")
        PENDING = "pending", gettext_noop("Waiting for the unit lead")
        APPROVED = "approved", gettext_noop("Approved")
        REJECTED = "rejected", gettext_noop("Rejected")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="imported_unit_rows")
    imported = models.OneToOneField("makerspaces.ImportedMember", on_delete=models.CASCADE, related_name="unit_row")
    unit = models.ForeignKey(MemberUnit, on_delete=models.PROTECT, related_name="imported_rows")
    review_status = models.CharField(max_length=16, choices=Review.choices, default=Review.NOT_REQUIRED)
    reviewed_at = models.DateTimeField(null=True, blank=True)
