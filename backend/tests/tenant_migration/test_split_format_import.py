"""A PORTABLE archive one format back (the split accounts) converts on import (Q11; local only).

Format 1 written before one account per person has no roster ``track`` and names each
staff account's tenant in ``staff_makerspace_id``; such a staff account imports as a person
holding staff-track rows. Any other format version is refused.
"""

import csv
import json

import pytest

from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.tenant_migration.archive_envelope import FORMAT_VERSION, READABLE_FORMAT_VERSIONS
from apps.tenant_migration.archive_stream import PortableArchive
from apps.tenant_migration.insertion_errors import ArchiveFormatError
from apps.tenant_migration.materialization import materialize_tenant
from tests.accounts.account_factories import grant_staff_role
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case

pytestmark = pytest.mark.django_db(transaction=True)


def _rewrite(path, transform, columns):
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns(rows))
        writer.writeheader()
        writer.writerows(transform(row) for row in rows)


def _as_split_format(root, space, staff):
    (root / "migration-manifest.json").write_text(json.dumps({"format_version": 1}), encoding="utf-8")
    roster = root / "members" / "roster.csv"
    _rewrite(roster, lambda row: {key: value for key, value in row.items() if key != "track"},
             lambda rows: [name for name in rows[0] if name != "track"])
    users = root / "global" / "users.csv"
    _rewrite(users, lambda row: {**row, "account_kind": "staff" if row["id"] == str(staff.pk) else row["account_kind"],
                                 "staff_makerspace_id": str(space.pk) if row["id"] == str(staff.pk) else ""},
             lambda rows: [*rows[0], "staff_makerspace_id"])


def test_only_the_current_and_previous_portable_versions_are_readable():
    assert FORMAT_VERSION == 2 and READABLE_FORMAT_VERSIONS == {1, 2}


def test_a_split_format_staff_account_imports_as_a_person_with_staff_rows():
    with enabled_encryption():
        owner = make_user("split-owner")
        source = make_space("split-source")
        state = {}

        def prepare(space, _user, _request):
            staff = make_user("split-staff")
            grant_staff_role(staff, space, role_slug="booking_manager")
            state["staff"] = staff

        with portable_import_case(source, owner, prepare_source=prepare) as case:
            _as_split_format(case.root, source, state["staff"])
            rows = {row["user_id"]: row for row in PortableArchive(case.root).rows("makerspaces.MakerspaceMembership")}
            assert rows[str(state["staff"].pk)]["track"] == "staff"
            assert rows[str(owner.pk)]["track"] == "community"
            case.decide_walk_in(owner)
            case.decide_walk_in(state["staff"])
            result = materialize_tenant(case.root, case.job, case.carried, target_identity={"slug": "split-target"})
        target = Makerspace.objects.get(pk=result.target_makerspace_id)
        staff_row = MakerspaceMembership.staff_tracks.get(makerspace=target)
        assert staff_row.assigned_role.slug == "booking_manager" and staff_row.status == "active"
        assert staff_row.user.account_kind == "member"


def test_split_columns_in_a_current_archive_are_refused():
    with enabled_encryption():
        owner = make_user("split-refused-owner")
        source = make_space("split-refused")
        with portable_import_case(source, owner) as case:
            _as_split_format(case.root, source, owner)
            (case.root / "migration-manifest.json").write_text(json.dumps({"format_version": 2}), encoding="utf-8")
            with pytest.raises(ArchiveFormatError, match="drifted"):
                list(PortableArchive(case.root).rows("makerspaces.MakerspaceMembership"))
