"""S-B: a staff device grant follows ANY primary method (#62; accounts 0054)."""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from rest_framework.test import APIClient

from apps.accounts.models import DeviceGrant
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_staff
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.test_device_staff_grants import PASSWORD, device_login, verify

pytestmark = pytest.mark.django_db


def _member_grant(settings, monkeypatch):
    space = Makerspace.objects.create(name="Primary Space", slug="primary-space")
    person = make_staff(space, username="primary-staff", password=PASSWORD)
    _row, secret = enrolled(person)
    client = APIClient()
    first = device_login(client, person, settings, monkeypatch)
    assert verify(client, first, secret).status_code == 200
    return space, DeviceGrant.objects.get(user=person)


def _copy(grant, **changes):
    fields = {f.attname: getattr(grant, f.attname) for f in DeviceGrant._meta.concrete_fields
              if f.attname not in {"id", "created_at"}}
    fields.update(changes, attested_at=timezone.now(), last_used_at=timezone.now())
    return DeviceGrant.objects.create(**fields)


@pytest.mark.parametrize("method", ["password", "phone", "social"])
def test_staff_grant_accepts_every_primary_method(method, settings, monkeypatch):
    space, grant = _member_grant(settings, monkeypatch)
    staff = _copy(grant, authority="staff", staff_makerspace_id=space.pk, login_method=method)
    assert staff.login_method == method


def test_staff_grant_still_refuses_an_unknown_method(settings, monkeypatch):
    space, grant = _member_grant(settings, monkeypatch)
    with pytest.raises(IntegrityError), transaction.atomic():
        _copy(grant, authority="staff", staff_makerspace_id=space.pk, login_method="")
