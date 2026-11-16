import json
from types import SimpleNamespace

import pytest
from django.db import connection, transaction

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.backup.raw_projection import fixture_payload, raw_records
from apps.backup.slice_rows import SLICE_ROW_SPECS
from apps.backup.staff_shells import SHELL_TIMESTAMP, shell_fixture
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.staff_retirement import shell_values
from tests.backup.conftest import installed_producer_capability  # noqa: F401
from .p1_helpers import staff
from .p4_auth_helpers import staff_auth_history

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skip(reason="U-A1: separate staff accounts and their retired-shell account-context trigger no longer exist (staff is a staff-track membership on the person's one account), so there is no staff shell to reverse"),
]


def test_ordinary_connection_cannot_reverse_a_retired_staff_shell():
    from django.db import DatabaseError
    space = Makerspace.objects.create(name="Guard staff", slug="p4-staff-guard")
    operator, membership = staff(space)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.account_retirement_makerspace_id', %s, true)", [str(space.pk)])
        User.objects.filter(pk=operator.pk).update(**shell_values(operator.pk, SHELL_TIMESTAMP))
        membership.delete()
    with pytest.raises(DatabaseError), transaction.atomic():
        User.objects.filter(pk=operator.pk).update(staff_makerspace=space, retired_at=None, is_active=True)


