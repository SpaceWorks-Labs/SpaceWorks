"""Decision 220(e): retiring an offsite destination, rotating its credentials, pushing now and
rehydrating an archive need a recent server-owned re-authentication (403
`recent_reauth_required`); reads, probes and non-credential edits do not."""

import uuid

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.backup.models import BackupArchive
from tests.backup.offsite_test_support import make_destination, offsite_bucket  # noqa: F401  (fixture)
from tests.stage4.helpers import bearer_client

pytestmark = pytest.mark.django_db


def _unverified():
    """A superadmin on a real session token that has not re-authenticated."""
    actor = User.objects.create_superuser(username=f"reauth-{uuid.uuid4().hex}", password="x")
    return actor, bearer_client(actor)


def _refused(response):
    assert response.status_code == 403, response.content
    assert response.data["code"] == "recent_reauth_required"


def test_destructive_offsite_actions_need_a_recent_reauthentication(monkeypatch):
    actor, client = _unverified()
    destination = make_destination("cold")
    archive = BackupArchive.objects.create(scope="deployment", object_key=f"backup/{uuid.uuid4()}")
    monkeypatch.setattr("apps.backup.views_offsite.dispatch_offsite_push", lambda: True)
    _refused(client.post(reverse("admin-backup-destination-retire", args=[destination.pk])))
    _refused(client.post(reverse("admin-backup-destination-push")))
    _refused(client.post(reverse("admin-backup-archive-rehydrate", args=[archive.pk]),
                         {"destination": destination.pk}, format="json"))
    url = reverse("admin-backup-destination", args=[destination.pk])
    for credential in ({"secret_access_key": "new-secret"}, {"access_key_id": "AKIANEW"}):
        _refused(client.patch(url, credential, format="json"))
    destination.refresh_from_db()
    assert destination.retired_at is None and destination.get_secret_access_key() != "new-secret"
    assert not AuditLog.objects.filter(action__in=(
        "backup.destination_retired", "backup.offsite_push_requested", "backup.archive_rehydrate_requested",
        "backup.destination_updated")).exists()


def test_reads_stay_open_and_a_fresh_proof_unlocks_every_write(monkeypatch):
    # Owner rule 261 widened 220(e): even a non-credential edit (retention) is a write and now
    # needs the proof; only reads stay open without it.
    actor, client = _unverified()
    destination = make_destination("cold")
    url = reverse("admin-backup-destination", args=[destination.pk])
    assert client.get(reverse("admin-backup-destinations")).status_code == 200
    _refused(client.patch(url, {"retention_days": 30}, format="json"))
    client = bearer_client(actor, recent=True)
    monkeypatch.setattr("apps.backup.views_offsite.dispatch_offsite_push", lambda: True)
    assert client.patch(url, {"secret_access_key": "rotated"}, format="json").status_code == 200
    assert client.post(reverse("admin-backup-destination-push")).status_code == 202
    assert client.post(reverse("admin-backup-destination-retire", args=[destination.pk])).status_code == 200


def test_registering_a_destination_needs_a_recent_reauthentication(offsite_bucket):
    actor, client = _unverified()
    url = reverse("admin-backup-destinations")
    body = {"name": "new-cold", "endpoint_url": "https://example.r2.test", "bucket": offsite_bucket,
            "access_key_id": "AKIA-NEW", "secret_access_key": "new-secret"}
    _refused(client.post(url, body, format="json"))
    assert not AuditLog.objects.filter(action="backup.destination_created").exists()
    assert bearer_client(actor, recent=True).post(url, body, format="json").status_code == 201
