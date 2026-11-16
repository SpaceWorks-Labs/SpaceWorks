"""U-C merge engine: dispositions, shell, record, privilege diff, grace, repeat refusal, E003."""

import pytest
from django.utils import timezone

from apps.accounts import merge_registry
from apps.accounts.models import User
from apps.accounts.models_account_merge import AccountMergeIntent, AccountMergeRecord
from apps.accounts.models_mfa import UserMFA
from apps.accounts.models_mfa_grace import StaffMfaGrace
from apps.accounts.staff_identity import actor_ids_for, has_staff_role
from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.audit.verification import classify_audit_row
from apps.makerspaces.models import MakerspaceMembership
from tests.accounts.merge_helpers import (  # noqa: F401 -- fixtures
    client_for, confirm, converted, feed, keys_and_clean_cache, make_membership, outbox, person,
    proved_by_codes, space, url,
)
from tests.accounts.mfa_helpers import enrolled

pytestmark = pytest.mark.django_db


def _merge(outbox, survivor, source):
    client = client_for(survivor)
    intent = proved_by_codes(client, outbox, survivor, source.email, source.username)
    preview, done = confirm(client, intent)
    return client, intent, preview, done


def test_merge_walks_every_disposition(outbox, django_capture_on_commit_callbacks):
    a, b = space("me-a"), space("me-b")
    survivor = person("me-survivor")
    source = converted("me-source", makerspace=a)
    make_membership(survivor, b)
    loser = make_membership(source, b)                       # UNIQUE_RESOLVE, slot taken -> stays, revoked
    feed(a, source)                                         # UNIQUE_RESOLVE, free slot -> moves
    taken = feed(b, source)
    kept = feed(b, survivor)
    b.created_by = source                                   # REPOINT
    b.save(update_fields=["created_by"])
    history = audit.record(source, "makerspace.updated", makerspace=a, target=a)  # KEEP_ON_SHELL
    status = classify_audit_row(history)
    _row, _secret = enrolled(source)
    with django_capture_on_commit_callbacks(execute=True):
        _client, intent, preview, done = _merge(outbox, survivor, source)
    assert done.status_code == 200, done.data
    source.refresh_from_db()
    b.refresh_from_db()
    taken.refresh_from_db()
    loser.refresh_from_db()
    # The shell: inert, scrubbed, aliased to the survivor.
    assert source.account_kind == "staff" and source.merged_into_id == survivor.pk and not source.is_active
    assert source.username.startswith("merged-") and source.email == "" and source.merged_at is not None
    assert actor_ids_for(survivor) == {survivor.pk, source.pk}
    # Staff roles moved; the community slot the survivor holds stayed behind, revoked.
    assert has_staff_role(survivor, a.pk)
    assert loser.user_id == source.pk and loser.status == "revoked"
    assert MakerspaceMembership.objects.filter(user=survivor, makerspace=b).count() == 1
    assert b.created_by_id == survivor.pk
    assert taken.user_id == source.pk and taken.revoked_at is not None and kept.user_id == survivor.pk
    from apps.bookings.models_feed import BookingCalendarFeed
    assert BookingCalendarFeed.objects.filter(makerspace=a, user=survivor).exists()
    # History stays on the shell id; the row MAC still verifies the same way.
    history.refresh_from_db()
    assert history.actor_id == source.pk and classify_audit_row(history) == status
    # The source's factor never moves (Q3).
    assert UserMFA.objects.filter(user=source).exists() and not UserMFA.objects.filter(user=survivor).exists()
    record = AccountMergeRecord.objects.get(decision="merged", source=source)
    assert record.target_id == survivor.pk and record.state == "completed" and record.snapshot_ciphertext
    assert record.proof_method == "email_codes"
    assert done.data["roles_gained"][0]["makerspace"]["id"] == a.pk
    entry = AuditLog.objects.get(action="account.merged", actor=survivor)
    assert entry.meta["source_id"] == source.pk and entry.meta["proof_method"] == "email_codes"
    assert AccountMergeIntent.objects.get(pk=intent).state == "consumed"
    assert merge_registry.problems() == {"unclassified_relations": [], "unclassified_columns": [],
                                         "stale_relations": [], "stale_columns": []}
    assert {mail["to_email"] for mail in outbox if mail["event"] == "account_merged"} == {
        survivor.email, "me-source@staff.test"}


def test_preview_lists_privilege_diff_and_conflicts(outbox):
    a, b = space("pv-a"), space("pv-b")
    survivor = person("pv-survivor")
    from tests.accounts.account_factories import grant_staff_role
    grant_staff_role(survivor, b, role_slug="inventory_manager")
    source = converted("pv-source", makerspace=a)
    grant_staff_role(source, b, role_slug="machine_manager")
    client = client_for(survivor)
    intent = proved_by_codes(client, outbox, survivor, source.email, source.username)
    preview = client.get(url(intent, "preview")).data
    assert [row["makerspace"]["id"] for row in preview["privilege_diff"]["roles_gained"]] == [a.pk]
    assert [row["makerspace"]["id"] for row in preview["privilege_diff"]["duplicate_staff_rows"]] == [b.pk]
    assert {"model": "makerspaces.MakerspaceMembership", "field": "user_id", "kept_on_shell": 1} in preview["conflicts"]
    assert preview["grace_opens"] is False and len(preview["preview_sha256"]) == 64


def test_confirm_refuses_a_stale_preview(outbox):
    a = space("st-a")
    survivor, source = person("st-survivor"), converted("st-source")
    client = client_for(survivor)
    intent = proved_by_codes(client, outbox, survivor, source.email, source.username)
    preview = client.get(url(intent, "preview")).data
    make_membership(source, a)
    stale = client.post(url(intent, "confirm"), {"preview_sha256": preview["preview_sha256"]}, format="json")
    assert stale.status_code == 409 and stale.data["code"] == "preview_stale"
    assert User.objects.get(pk=source.pk).merged_into_id is None


def test_merge_into_staff_without_factor_opens_the_grace_once(outbox):
    a = space("gr-a")
    survivor, source = person("gr-survivor"), converted("gr-source", makerspace=a)
    _client, _intent, preview, done = _merge(outbox, survivor, source)
    assert preview.data["grace_opens"] and done.data["grace_opened"]
    grace = StaffMfaGrace.objects.get(user=survivor)
    assert grace.source == "merge" and timezone.timedelta(days=2, hours=23) < grace.ends_at - grace.started_at


def test_a_completed_merge_is_never_repeated(outbox):
    survivor, source = person("rp-survivor"), converted("rp-source")
    client, intent, _preview, done = _merge(outbox, survivor, source)
    assert done.status_code == 200
    again = client.post(url(intent, "confirm"), {"preview_sha256": "0" * 64}, format="json")
    assert again.status_code == 410 and again.data["code"] == "proof_expired"
    from apps.accounts.account_merge_eligibility import source_refusal
    assert source_refusal(User.objects.get(pk=source.pk), survivor) == "already_merged"


def test_confirm_needs_recent_reauthentication(outbox):
    from apps.accounts.models_reauthentication import ReauthenticationSession

    survivor, source = person("ra-survivor"), converted("ra-source")
    client = client_for(survivor)
    intent = proved_by_codes(client, outbox, survivor, source.email, source.username)
    preview = client.get(url(intent, "preview")).data
    ReauthenticationSession.objects.filter(user=survivor).delete()
    refused = client.post(url(intent, "confirm"), {"preview_sha256": preview["preview_sha256"]}, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "recent_reauth_required"


def test_unclassified_reference_refuses_the_merge(outbox, monkeypatch):
    survivor, source = person("uc-survivor"), converted("uc-source")
    client = client_for(survivor)
    intent = proved_by_codes(client, outbox, survivor, source.email, source.username)
    preview = client.get(url(intent, "preview")).data
    monkeypatch.setattr(merge_registry, "problems", lambda: {
        "unclassified_relations": [("x.Model", "user")], "unclassified_columns": [],
        "stale_relations": [], "stale_columns": []})
    refused = client.post(url(intent, "confirm"), {"preview_sha256": preview["preview_sha256"]}, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "merge_not_allowed"


def test_merge_suggested_flag(outbox):
    survivor, source = person("ms-survivor"), converted("ms-source")
    from apps.accounts.account_merge_eligibility import merge_suggested
    assert merge_suggested(source) and not merge_suggested(survivor)
    me = client_for(source).get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.data.get("user", me.data)["merge_suggested"] is True
