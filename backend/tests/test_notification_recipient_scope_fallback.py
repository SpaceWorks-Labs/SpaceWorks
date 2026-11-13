"""Action fallback and rule precedence respect each recipient person's type links."""
import pytest

from apps.accounts.rbac import Action
from apps.integrations.models_recipients import NotificationRecipient, NotificationRecipientKind
from apps.makerspaces.models import MakerspaceMembership
from tests.test_notification_recipient_scope import make_space, make_machine, make_role, make_member, emails

pytestmark = pytest.mark.django_db


# --- the action-based fallback is scoped too, but only where a role is really narrowed ---


def test_the_fallback_excludes_a_maintainer_whose_LINKS_do_not_cover_the_machine():
    """Falling back must not mail another team's machine detail.

    The action-based default predates machine scoping and is makerspace-wide, so once
    `has_selection` learned to fall through per subject, an uncovered printer alert would
    have reached every MANAGE_MACHINES holder -- including a laser-only maintainer who
    cannot open that machine in the console at all.
    """
    space = make_space("rulescope-fallback-links")
    laser = make_machine(space, "laser")
    printer = make_machine(space, "printer")
    laser_role = make_role(space, "laser-team", [Action.MANAGE_MACHINES])
    printer_role = make_role(space, "printer-team", [Action.MANAGE_MACHINES])
    laser_member = make_member("rulescope-fallback-laser", space, laser_role)
    MakerspaceMembership.staff_tracks.get(user=laser_member, makerspace=space).machine_type_scopes.create(machine_type=laser.machine_type)
    printer_member = make_member("rulescope-fallback-printer", space, printer_role)
    MakerspaceMembership.staff_tracks.get(user=printer_member, makerspace=space).machine_type_scopes.create(machine_type=printer.machine_type)

    # No rows at all: pure action-based fallback, now narrowed by each role's links.
    assert emails(space, printer) == [printer_member.email]
    assert emails(space, laser) == [laser_member.email]


def test_the_fallback_still_reaches_a_role_that_has_no_links_at_all():
    """NO LINKS MEANS UNCONFIGURED HERE, NOT "REACHES NOTHING".

    The opposite of the access rule, deliberately. For access, a machine-managing role with
    no links reaches no machine (fail closed). Applying that to notifications would mute a
    space's maintenance mail the instant an alert named a machine, which is the one outcome
    this module forbids -- so the fallback filter only removes a role whose links genuinely
    exclude the subject.
    """
    space = make_space("rulescope-fallback-unlinked")
    printer = make_machine(space, "printer")
    unlinked = make_role(space, "unlinked-team", [Action.MANAGE_MACHINES])
    member = make_member("rulescope-fallback-unlinked-member", space, unlinked)

    assert emails(space, printer) == [member.email]


def test_a_broad_rule_scoped_elsewhere_does_not_shadow_a_narrow_covering_rule():
    """Precedence applies only among rows that COVER the subject.

    A members-wide row scoped to the printers used to be chosen for a laser alert, fail its
    coverage check, and skip the membership -- so the laser-scoped role row that did cover
    it was never consulted and the alert reached nobody. 6c2 makes this pairing ordinary: a
    delegated laser rule sits beside a preserved space-wide members rule by design.
    """
    space = make_space("rulescope-shadow")
    laser = make_machine(space, "laser")
    printer = make_machine(space, "printer")
    role = make_role(space, "laser-team", [Action.MANAGE_MACHINES])
    member = make_member("rulescope-shadow-member", space, role)
    MakerspaceMembership.staff_tracks.get(user=member, makerspace=space).machine_type_scopes.create(machine_type=laser.machine_type)

    printer_members_rule = NotificationRecipient.objects.create(
        makerspace=space,
        feature="maintenance",
        event="logged",
        kind=NotificationRecipientKind.MEMBERS,
    )
    printer_members_rule.machine_type_scopes.create(machine_type=printer.machine_type)
    laser_role_rule = NotificationRecipient.objects.create(
        makerspace=space,
        feature="maintenance",
        event="logged",
        kind=NotificationRecipientKind.ROLE,
        role=role,
    )
    laser_role_rule.machine_type_scopes.create(machine_type=laser.machine_type)

    assert emails(space, laser) == [member.email]
