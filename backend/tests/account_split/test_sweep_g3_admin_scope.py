"""Control-plane staff identities follow their owning tenant, including FK widgets."""

from types import SimpleNamespace

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.models import User
from apps.evidence.models import EvidencePhoto
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_staff


pytestmark = pytest.mark.django_db


@pytest.mark.skip(reason="U-A1: staff authority is a staff-track membership on ONE account per person, not an account "
                  "owned by a tenant, so there are no 'inaccessible staff accounts' to hide and the admin has no per-tenant row gate")
def test_user_rows_and_plain_foreign_key_widgets_hide_inaccessible_staff():
    visible = Makerspace.objects.create(name='Visible', slug='g3-visible')
    archived = Makerspace.objects.create(name='Archived', slug='g3-archived', archived_at=timezone.now())
    own_staff = make_staff(visible, username='g3-visible-staff')
    archived_staff = make_staff(archived, username='g3-archived-staff')
    member = User.objects.create_user(username='g3-member')
    operator = User.objects.create_superuser(username='g3-operator')
    request = RequestFactory().get('/control/accounts/user/')
    request.user = operator
    request.resolver_match = SimpleNamespace(url_name='accounts_user_changelist')
    model_admin = admin.site._registry[User]
    visible_ids = set(model_admin.get_queryset(request).values_list('pk', flat=True))
    assert {own_staff.pk, member.pk, operator.pk} <= visible_ids
    assert archived_staff.pk not in visible_ids
    assert not model_admin.has_change_permission(request, archived_staff)
    evidence_admin = admin.site._registry[EvidencePhoto]
    field = evidence_admin.formfield_for_foreignkey(EvidencePhoto._meta.get_field('uploaded_by'), request)
    ids = set(field.queryset.values_list('pk', flat=True))
    assert {own_staff.pk, member.pk, operator.pk} <= ids
    assert archived_staff.pk not in ids


@pytest.mark.skip(reason="U-A1: staff authority is a staff-track membership on ONE account per person, not an account "
                  "owned by a tenant, so there are no 'inaccessible staff accounts' to hide and the admin has no per-tenant row gate")
def test_mixed_account_bulk_action_checks_only_actual_staff_tenants(monkeypatch):
    space = Makerspace.objects.create(name='Mixed', slug='g3-mixed')
    staff = make_staff(space, username='g3-mixed-staff')
    member = User.objects.create_user(username='g3-mixed-member')
    platform = User.objects.create_superuser(username='g3-mixed-platform')
    checked = []
    monkeypatch.setattr('apps.tenant_migration.gate_runtime.assert_write_allowed', checked.append)
    admin.site._registry[User]._assert_source_gate(
        RequestFactory().post('/control/accounts/user/'),
        queryset=User.objects.filter(pk__in=[staff.pk, member.pk, platform.pk]),
    )
    assert checked == [space.pk]
