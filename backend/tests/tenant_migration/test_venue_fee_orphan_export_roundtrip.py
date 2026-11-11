"""An exported venue-fee debt must not be silently dropped during import."""
from django.utils import timezone
from datetime import timedelta

import pytest

from apps.events.models import Event, EventVenueFee
from apps.makerspaces.models import Makerspace
from apps.payments.models import Payment
from apps.tenant_migration.insertion_errors import VenueFeeDebtProvenanceUnavailable
from apps.tenant_migration.materialization import materialize_tenant
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case


@pytest.mark.django_db(transaction=True)
def test_exported_orphan_venue_debt_refuses_before_target_or_object_staging(monkeypatch):
    with enabled_encryption():
        actor = make_user("venue-orphan-export-owner")
        space = make_space("venue-orphan-export-space")
        saved = {}

        def seed(maker, user, _request):
            start = timezone.now() + timedelta(days=2)
            event = Event.objects.create(makerspace=maker, title="Venue", starts_at=start,
                                         ends_at=start + timedelta(hours=1))
            fee = EventVenueFee.objects.create(makerspace=maker, event=event, payer=user,
                                               mode="custom", basis="flat", amount="10.00")
            payment = Payment.objects.create(
                makerspace=maker, subject_type="event_venue_fee", subject_id=fee.pk,
                member=user, created_by=user, amount="10.00", currency="usd", provider="unclaimed",
            )
            saved["payment_id"] = payment.pk
            fee.delete()  # Payment's retained ledger subject is intentionally not a foreign key.

        with portable_import_case(space, actor, prepare_source=seed) as case:
            from apps.tenant_migration import materialization
            calls = []
            monkeypatch.setattr(materialization, "prepare_import_objects", lambda *_: calls.append("objects"))
            monkeypatch.setattr(materialization, "create_target_makerspace", lambda *_a, **_kw: calls.append("target"))
            with pytest.raises(VenueFeeDebtProvenanceUnavailable):
                materialize_tenant(case.root, case.job, case.carried,
                                   target_identity={"slug": "venue-orphan-refused-target"})
            assert calls == []
            assert Payment.objects.filter(pk=saved["payment_id"], makerspace=space).exists()
            assert not Makerspace.objects.filter(slug="venue-orphan-refused-target").exists()
