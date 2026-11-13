import csv
from datetime import timedelta
from io import BytesIO, StringIO
from types import SimpleNamespace

import pytest
from tests.accounts.account_factories import make_membership  # presence needs a community membership
from django.utils import timezone
from openpyxl import load_workbook

from apps.accounts.models import User
from apps.audit.services import record
from apps.makerspaces.models import MakerspaceMembership
from apps.operations import reports
from apps.operations.platform_scope import _platform_context_for_view
from apps.operations.report_definitions_j import J_REPORT_DEFINITIONS
from apps.operations.report_exports import csv_bytes, xlsx_bytes
from apps.operations.report_exports_provenance import build_provenance
from apps.operations.report_registry import REPORT_REGISTRY
from apps.presence.models import PresenceSession
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import make_member, make_space, make_user


@pytest.mark.django_db
@pytest.mark.parametrize("key", [d.key for d in J_REPORT_DEFINITIONS])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_every_j_builder_export_uses_declared_fields_and_passes_disclosure_guard(key, fmt):
    space = make_space("j-export")
    actor = make_member("j-export-manager", space)
    membership = make_membership(actor, space)
    at = timezone.now() - timedelta(hours=2)
    PresenceSession.objects.create(makerspace=space, member=actor, membership=membership,
                                    started_at=at, expires_at=at + timedelta(hours=1))
    record(actor, "user.password_changed", makerspace=space, meta={"secret": "private"})
    definition = REPORT_REGISTRY[key]
    ctx = None
    space_id = space.pk
    if definition.platform_only or key == "organization-membership":
        operator = make_user("j-export-operator", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE)
        ctx, space_id = _platform_context_for_view(SimpleNamespace(user=operator)), None
    matrix = reports.report_rows(key, space_id, actor=actor, platform_context=ctx)
    assert set(matrix[0]) <= set(definition.fields)
    if key == "module-operational-health":
        from apps.operations.report_fields_j import HEALTH_FIELDS
        assert tuple(matrix[0]) == HEALTH_FIELDS
    assert_report_disclosure_safe(matrix)
    provenance = build_provenance(key, version=definition.version, makerspace_id=space_id, generated_by="builder")
    if fmt == "csv":
        payload = csv_bytes(matrix, provenance=provenance)
        decoded = list(csv.reader(StringIO(payload.decode().split("\n", 1)[1])))
    else:
        book = load_workbook(BytesIO(xlsx_bytes(matrix, provenance=provenance)), read_only=True)
        decoded = [list(row) for row in book["Report"].iter_rows(values_only=True)]
    assert decoded[0] == list(matrix[0])
    assert set(decoded[0]) <= set(definition.fields)
    assert_report_disclosure_safe(decoded)
