"""Local checks for the `seed_showcase` management command (not committed)."""
from io import StringIO
from datetime import timedelta

from django.utils import timezone

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.bookings.models import Booking
from apps.evidence.models import EvidencePhoto
from apps.hardware_requests.models import HardwareRequest
from apps.inventory.models import InventoryAsset, InventoryProduct
from apps.machines.models import Machine, MachineServiceRequest
from apps.makerspaces.models import Makerspace, MemberCard
from apps.boxes.models import QrCode
from apps.operations.management.commands import _showcase_data as data
from apps.operations.management.commands._showcase_l3 import seed_member_cards
from apps.organizations.models import OrganizationMakerspace
from apps.payments.models import Payment
from apps.payments.models_settlement import ManualSettlement


def _assert_showcase(space):
    cards = MemberCard.objects.filter(makerspace=space, revoked_at__isnull=True)
    assert set(cards.values_list("membership__user__username", flat=True)) == {username for username, _name in data.MEMBERS}
    assert QrCode.objects.filter(makerspace=space, target_type="member_card", target_id__in=cards.values("pk"), status="active").count() == cards.count()
    assert AuditLog.objects.filter(makerspace=space, action="member_card.issued").count() == cards.count()
    statuses = set(HardwareRequest.objects.filter(makerspace=space).values_list("status", flat=True))
    assert statuses == {
        "pending_approval", "accepted", "issued", "partially_returned", "returned",
        "rejected", "closed_with_issue",
    }
    issued = HardwareRequest.objects.filter(makerspace=space, status="issued")
    assert issued.count() >= 2 and all(r.issue_evidence_id for r in issued)
    photos = EvidencePhoto.objects.filter(makerspace=space)
    assert photos.filter(evidence_type="issue").count() == 6
    assert photos.filter(evidence_type="return").count() == 3
    assert not photos.exclude(consumption_state="consumed").exists()

    products = InventoryProduct.objects.filter(makerspace=space)
    assert products.count() >= 30
    assert set(products.values_list("public_availability_mode", flat=True)) == {
        "exact_count", "status_only", "hidden"}
    assert products.filter(tracking_mode="individual").count() == 7
    assert InventoryAsset.objects.filter(makerspace=space).count() == 18

    jobs = set(MachineServiceRequest.objects.filter(makerspace=space).values_list("status", flat=True))
    assert {"pending", "accepted", "in_progress", "completed", "collected"} <= jobs
    machines = Machine.objects.filter(makerspace=space)
    assert machines.count() == 10 and machines.filter(status="maintenance").count() == 1
    assert machines.filter(status="running").count() == 2
    assert not machines.filter(is_public=False).exists()

    settled = Payment.objects.filter(makerspace=space, status="paid_offline")
    # The six member dues the seed settles, plus offline payments other showcase sections record;
    # every offline-paid row still carries its append-only receipt.
    assert settled.count() >= 6
    assert ManualSettlement.objects.filter(payment__in=settled).count() == settled.count()
    assert Payment.objects.filter(makerspace=space, status="pending", provider="unclaimed").exists()
    assert set(Booking.objects.filter(space__makerspace=space).values_list("status", flat=True)) == {
        "confirmed", "pending"}
    assert OrganizationMakerspace.objects.get(makerspace=space, relationship="owner").organization.name \
        == "Tinkerspace Collective"
    assert User.objects.get(username="felix_grant").access_status == "restricted"
    assert "security.staff_mfa_required" not in space.enabled_features
    assert "machines.public_detail" in space.enabled_features
    from apps.events.judging.models_definitions import JudgingRound
    from apps.events.judging.models_pairwise import JudgePairwiseComparison, JudgePairwiseCursor
    from apps.events.judging.pairwise_projection import standings
    round = JudgingRound.objects.get(event__makerspace=space, key="finals")
    assert round.mode == "pairwise" and round.state == "open" and "events.pairwise_judging" in space.enabled_features
    # A multi-day release audit must keep role-derived judge authority live.
    assert round.event.ends_at >= timezone.now() + timedelta(days=6)
    assert JudgePairwiseComparison.objects.filter(round=round).count() == 5
    assert JudgePairwiseCursor.objects.filter(round=round).count() == 3
    assert AuditLog.objects.filter(makerspace=space, action="event.programme.pairwise_compared").count() == 5
    assert len(standings(round)["rows"]) == 4



@pytest.fixture(autouse=True)
def builtin_machine_types(request):
    """A transactional test earlier in the run flushes migration-seeded rows; the
    showcase seed reads the global built-in machine types, so restore them."""
    if request.node.get_closest_marker("django_db") is None:
        return
    from importlib import import_module
    from django.apps import apps as django_apps
    import_module("apps.machines.migrations.0002_seed_builtin_machine_types").seed_builtins(django_apps, None)
    import_module("apps.machines.migrations.0017_seed_machine_type_metering_packs").forward(django_apps, None)


@pytest.mark.django_db(transaction=True)
def test_seed_showcase_builds_every_state_and_rebuilds_with_reset(settings, tmp_path):
    settings.DEBUG = True
    credentials = tmp_path / "build" / "credentials.txt"
    out = StringIO()
    call_command("seed_showcase", credentials_file=str(credentials), stdout=out)
    password = credentials.read_text(encoding="utf-8").splitlines()[1]
    assert password and password not in out.getvalue()
    space = Makerspace.objects.get(slug="tinkerspace")
    _assert_showcase(space)
    # The seed's member jobs use the same owner field as normal public submit.
    from django.urls import reverse
    from tests.events.collab_helpers import client_for
    job = MachineServiceRequest.objects.get(makerspace=space, title="Planter drip tray")
    assert job.member_id == job.requester_id
    member_detail = reverse("member-machine-job-detail", args=[job.pk])
    owned = client_for(job.requester).get(member_detail)
    assert owned.status_code == 200 and owned.data["id"] == job.pk
    other = User.objects.get(username="noor_rahman")
    assert other.pk != job.member_id
    assert client_for(other).get(member_detail).status_code == 404
    original_cards = list(MemberCard.objects.filter(makerspace=space).order_by("pk").values_list("pk", flat=True))
    manager = User.objects.get(username="tinker_manager")
    members = {user.username: user for user in User.objects.filter(username__in=[name for name, _ in data.MEMBERS])}
    seed_member_cards(space, manager, members)
    assert list(MemberCard.objects.filter(makerspace=space).order_by("pk").values_list("pk", flat=True)) == original_cards
    assert AuditLog.objects.filter(makerspace=space, action="member_card.issued").count() == len(original_cards)
    for username in ("tinker_root", "tinker_manager", "tinker_desk", "asha_menon"):
        assert User.objects.get(username=username).check_password(password)
    assert AuditLog.objects.filter(makerspace=space, action="request.issued").exists()

    with pytest.raises(CommandError, match="--reset"):
        call_command("seed_showcase", password="another-pass-123")

    call_command("seed_showcase", password="another-pass-123", reset=True, stdout=StringIO())
    rebuilt = Makerspace.objects.get(slug="tinkerspace")
    assert rebuilt.pk != space.pk
    _assert_showcase(rebuilt)
    assert User.objects.get(username="tinker_manager").check_password("another-pass-123")


@pytest.mark.django_db
def test_seed_showcase_refusals_write_nothing(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="--allow-production-demo"):
        call_command("seed_showcase", password="x-pass-12345")
    settings.DEBUG = True
    with pytest.raises(CommandError, match="--credentials-file"):
        call_command("seed_showcase")
    assert not Makerspace.objects.filter(slug="tinkerspace").exists()
    assert not User.objects.filter(username="tinker_root").exists()
