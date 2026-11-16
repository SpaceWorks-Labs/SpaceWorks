"""makerspaces/0116 backfill, called directly on a head database (#124: no migration rollback)."""
import importlib
from datetime import timedelta

import pytest
from django.apps import apps
from django.utils import timezone

from apps.makerspaces.models import MakerspaceMembership, MembershipTerm, MembershipTermStatusEvent
from tests.makerspaces.l4_helpers import member, plan, space_with_manager

pytestmark = pytest.mark.django_db
backfill = importlib.import_module("apps.makerspaces.migrations.0117_membership_lifecycle_backfill")


def test_backfill_numbers_classifies_and_seeds_history():
    space, _manager = space_with_manager("bf")
    monthly = plan(space)
    now = timezone.now()
    first, second = member("bf-a", space), member("bf-b", space)
    old = MembershipTerm.objects.create(membership=first, plan=monthly, starts_at=now - timedelta(days=100),
                                        ends_at=now - timedelta(days=70), status="expired")
    MembershipTerm.objects.create(membership=first, plan=monthly, starts_at=now - timedelta(days=10),
                                  ends_at=now + timedelta(days=20))
    MembershipTerm.objects.create(membership=second, plan=monthly, starts_at=now - timedelta(days=5),
                                  ends_at=now + timedelta(days=25), status="cancelled")
    MakerspaceMembership.objects.filter(pk__in=[first.pk, second.pk]).update(member_number=None)
    backfill.number_members(apps)
    backfill.classify_terms(apps)
    backfill.backfill_history(apps)
    numbers = dict(MakerspaceMembership.objects.filter(pk__in=[first.pk, second.pk]).values_list("pk", "member_number"))
    assert sorted(numbers.values()) == [1, 2] and numbers[first.pk] == 1
    kinds = list(MembershipTerm.objects.filter(membership=first).order_by("starts_at").values_list("kind", flat=True))
    assert kinds == ["new", "reinstatement"]
    assert list(MembershipTermStatusEvent.objects.filter(term=old).values_list("status", flat=True)) == ["active", "lapsed"]
    statuses = set(MembershipTermStatusEvent.objects.filter(membership=second).values_list("status", flat=True))
    assert statuses == {"active", "cancelled"}
