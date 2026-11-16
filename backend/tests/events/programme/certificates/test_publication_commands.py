from uuid import uuid4
import pytest
from rest_framework.exceptions import NotFound
from apps.events.certificates.publication import set_policy
from apps.events.certificates.verification import project
from apps.events.credentials.errors import ProgrammeConflict
from tests.events.programme.certificates.test_subjects_verification import certificate
from tests.events.checkin_helpers import make_staff

pytestmark = pytest.mark.django_db(transaction=True)


def test_explicit_legacy_opt_in_replays_and_withdrawal_hides_previously_public_id():
    event, _member, row = certificate()
    row.public_verification_enabled = False
    row.save(update_fields=("public_verification_enabled",))
    actor, op = make_staff(event.makerspace), uuid4()
    values = dict(actor=actor, operation_id=op, expected_version=event.version, enabled=True, certificate_ids=[row.pk])
    first = set_policy(event.pk, **values)
    assert set_policy(event.pk, **values) == first
    assert project(row.serial)["status"] == "valid"
    with pytest.raises(ProgrammeConflict):
        set_policy(event.pk, **{**values, "certificate_ids": []})
    set_policy(event.pk, actor=actor, operation_id=uuid4(), expected_version=first["version"], enabled=False)
    with pytest.raises(NotFound):
        project(row.serial)
