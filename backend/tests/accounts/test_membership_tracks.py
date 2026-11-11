"""Membership tracks: fail-closed managers, per-track status, role writes, manager guard."""

import ast
from pathlib import Path

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

import apps.makerspaces
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.role_membership_writes import replace_membership_roles

from .ua1_helpers import community, person, platform, space, staff_row

pytestmark = pytest.mark.django_db
APPS_DIR = Path(apps.makerspaces.__file__).resolve().parent.parent
# Whole-tenant capture, restore, export, purge and the managers themselves may read
# every track; everything else picks one track explicitly.
ALL_TRACKS_ALLOWLIST = ("backup/", "tenant_migration/", "data_export/", "makerspaces/lifecycle_purge",
                        "makerspaces/membership_managers.py", "makerspaces/models_memberships.py")


def test_default_manager_and_reverse_relations_are_community_only():
    makerspace, user = space("tracks"), person("tracks")
    member = community(user, makerspace)
    staff = staff_row(user, makerspace, "inventory_manager")
    assert list(MakerspaceMembership.objects.filter(user=user)) == [member]
    assert list(user.makerspace_memberships.all()) == [member]
    assert list(makerspace.memberships.filter(user=user)) == [member]
    assert list(MakerspaceMembership.staff_tracks.filter(user=user)) == [staff]
    assert MakerspaceMembership.track_manager("staff").get(pk=staff.pk) == staff
    assert MakerspaceMembership.all_tracks.filter(user=user).count() == 2


def test_status_is_per_track():
    makerspace, user = space("status"), person("status")
    member = community(user, makerspace)
    staff = staff_row(user, makerspace, "event_manager", status="revoked")
    assert member.status == "active" and staff.status == "revoked"


def test_role_writes_follow_the_track():
    makerspace, user, root = space("writes"), person("writes"), platform()
    member = community(user, makerspace)
    with pytest.raises(ValidationError):
        replace_membership_roles(membership=member, roles=[makerspace.roles.get(slug="event_manager")],
                                 actor=root, reason="test")
    staff = staff_row(user, makerspace, "event_manager")
    with pytest.raises(ValidationError):
        replace_membership_roles(membership=staff, roles=[makerspace.roles.get(slug="member")],
                                 actor=root, reason="test")
    changes = replace_membership_roles(
        membership=staff, roles=[makerspace.roles.get(slug=slug) for slug in ("event_manager", "booking_manager")],
        actor=root, reason="test")
    assert changes["after"] == ["event_manager", "booking_manager"]


def test_only_the_superadmin_changes_a_space_manager_row():
    makerspace, manager, other = space("sm"), person("sm"), person("sm-other")
    peer = staff_row(person("peer"), makerspace, "space_manager")
    row = staff_row(manager, makerspace, "event_manager")
    sm_role = makerspace.roles.get(slug="space_manager")
    with pytest.raises(PermissionDenied) as caught:
        replace_membership_roles(membership=row, roles=[sm_role], actor=peer.user, reason="test")
    assert caught.value.get_codes() == "space_manager_superadmin_only"
    with pytest.raises(PermissionDenied):
        replace_membership_roles(membership=peer, roles=[makerspace.roles.get(slug="event_manager")],
                                 actor=other, reason="test")
    replace_membership_roles(membership=row, roles=[sm_role], actor=platform(), reason="test")


def _all_tracks_sites():
    sites = []
    for path in APPS_DIR.rglob("*.py"):
        relative = path.relative_to(APPS_DIR).as_posix()
        if "migrations" in path.parts or relative.startswith(ALL_TRACKS_ALLOWLIST):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            receiver = getattr(node.value, "id", None) or getattr(node.value, "attr", None)
            if node.attr == "all_tracks" or (
                    node.attr == "_base_manager" and receiver == "MakerspaceMembership"):
                sites.append(f"{relative}:{node.lineno}")
    return sites


def test_unfiltered_membership_reads_stay_inside_the_allowlist():
    assert _all_tracks_sites() == []
