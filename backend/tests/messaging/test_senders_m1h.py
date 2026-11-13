from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.db import close_old_connections, transaction
from django.utils import timezone

from apps.integrations.messaging.senders import (
    SenderInUse, callback_credentials, reserve_sender, retire_sender, wipe_retired_credentials,
)
from apps.integrations.models import MessagingSenderCredential


@pytest.mark.django_db
def test_rotation_overlap_and_reactivation(space):
    kwargs = dict(sender_key="meta:business:phone", channel="whatsapp", owner="makerspace", makerspace=space)
    identity = reserve_sender(**kwargs, webhook_secret="one")
    reserve_sender(**kwargs, webhook_secret="two")
    assert list(identity.credentials.order_by("version").values_list("version", flat=True)) == [1, 2]
    assert identity.credentials.get(version=1).retired_at is not None
    candidates = callback_credentials(channel="whatsapp", owner="makerspace", makerspace_id=space.pk)
    assert {row.get_secret("webhook_secret") for row in candidates} == {"one", "two"}
    MessagingSenderCredential.objects.filter(identity=identity, version=1).update(retired_at=timezone.now() - timedelta(days=15))
    assert wipe_retired_credentials() == 1
    assert identity.credentials.get(version=1).webhook_secret == ""
    retire_sender(identity)
    identity.refresh_from_db()
    assert not identity.active
    reserve_sender(**kwargs, webhook_secret="three")
    identity.refresh_from_db()
    assert identity.active and identity.retired_at is None
    assert identity.credentials.get(version=3).get_secret("webhook_secret") == "three"


@pytest.mark.django_db(transaction=True)
def test_two_connections_cannot_claim_the_same_sender(space):
    from apps.makerspaces.models import Makerspace
    other = Makerspace.objects.create(name="Other", slug="other-messaging")

    from threading import Barrier
    ready = Barrier(2)

    def claim(tenant_id):
        close_old_connections()
        try:
            tenant = Makerspace.objects.get(pk=tenant_id)
            ready.wait(timeout=10)
            reserve_sender(sender_key="meta:shared:phone", channel="whatsapp", owner="makerspace",
                           makerspace=tenant, webhook_secret="secret")
            return "claimed"
        except SenderInUse:
            return "sender_in_use"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, [space.pk, other.pk]))
    assert sorted(results) == ["claimed", "sender_in_use"]


@pytest.mark.django_db(transaction=True)
def test_sender_advisory_lock_serializes_separate_connections():
    from threading import Event
    from apps.integrations.messaging.locks import lock_whatsapp_sender
    held, started, release, acquired = Event(), Event(), Event(), Event()

    def first():
        close_old_connections()
        try:
            with transaction.atomic():
                lock_whatsapp_sender("meta:sender:phone")
                held.set()
                assert release.wait(10)
        finally:
            close_old_connections()

    def second():
        close_old_connections()
        try:
            assert held.wait(10)
            with transaction.atomic():
                started.set()
                lock_whatsapp_sender("meta:sender:phone")
                acquired.set()
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        one, two = pool.submit(first), pool.submit(second)
        try:
            assert started.wait(10)
            assert not acquired.wait(0.1)
        finally:
            release.set()
        one.result(timeout=10)
        two.result(timeout=10)
    assert acquired.is_set()


@pytest.mark.django_db
def test_retired_sender_is_reserved_during_overlap_and_can_transfer_after_wipe(space):
    from apps.makerspaces.models import Makerspace
    from apps.integrations.models import MessagingSenderIdentity
    other = Makerspace.objects.create(name="Replacement", slug="replacement-messaging")
    identity = reserve_sender(sender_key="meta:released:phone", channel="whatsapp", owner="makerspace",
                              makerspace=space, webhook_secret="old-secret")
    retire_sender(identity)
    kwargs = dict(sender_key=identity.sender_key, channel="whatsapp", owner="makerspace", makerspace=other,
                  webhook_secret="replacement-secret")
    with pytest.raises(SenderInUse):
        reserve_sender(**kwargs)
    cutoff = timezone.now() - timedelta(days=15)
    MessagingSenderIdentity.objects.filter(pk=identity.pk).update(retired_at=cutoff)
    MessagingSenderCredential.objects.filter(identity=identity).update(retired_at=cutoff)
    claimed = reserve_sender(**kwargs)
    assert claimed.pk == identity.pk and claimed.makerspace_id == other.pk
    assert claimed.credentials.get(version=1).webhook_secret == ""
    assert claimed.credentials.get(version=2).get_secret("webhook_secret") == "replacement-secret"
