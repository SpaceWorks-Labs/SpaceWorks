"""Lane r2-platform-overview (#183A): the superadmin platform overview.

Local, untracked (#175): written in the coding phase, run in the test phase on the combined tree.
Covers: superadmin only, per-space sums equal the totals, money per currency, module-off hiding,
the excluded-spaces toggle, no PII, the audited export and the "computing" state.
"""

import json
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.operations.platform_overview import build_platform_overview
from apps.operations.platform_overview_cache import cache_key
from apps.operations.platform_overview_window import resolve_window
from apps.payments.models import Payment
from tests.return_helpers import authenticated_client, make_member, make_space, make_user

pytestmark = pytest.mark.django_db

URL = "/api/v1/admin/platform/overview"
EXPORT = f"{URL}/export"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def superadmin():
    return make_user(f"ovr-root-{uuid.uuid4().hex[:6]}", role=User.Role.SUPERADMIN)


def space(prefix, *, modules=None, features=None):
    row = make_space(f"{prefix}-{uuid.uuid4().hex[:6]}")
    if modules is not None:
        row.enabled_modules = sorted(set(row.enabled_modules or []) | set(modules))
    if features is not None:
        row.enabled_features = sorted(set(row.enabled_features or []) | set(features))
    row.save(update_fields=["enabled_modules", "enabled_features"])
    return row


def without(row, *modules):
    row.enabled_modules = sorted(set(row.enabled_modules or []) - set(modules))
    row.save(update_fields=["enabled_modules"])


def member(row, name=None):
    return make_member(name or f"ovr-m-{uuid.uuid4().hex[:6]}", row, membership_role="member", role="requester")


def payment(row, payer, amount, currency, status=Payment.Status.PENDING):
    membership = MakerspaceMembership.objects.get(makerspace=row, user=payer)
    return Payment.objects.create(
        makerspace=row, subject_type=Payment.SubjectType.MAKERSPACE_MEMBERSHIP, subject_id=membership.pk,
        member=payer, amount=Decimal(amount), currency=currency, status=status, created_by=payer,
        subject_label="Membership dues")


def overview(*, include_excluded=False, preset="all_time"):
    return build_platform_overview(resolve_window(preset), include_excluded=include_excluded)


def block(data, key):
    return next((item for item in data["blocks"] if item["key"] == key), None)


def ours(data, *spaces):
    """Rows of only the spaces this test made (other tests' rows may share the database)."""
    ids = {row.pk for row in spaces}
    return [row for row in data["spaces"] if row["id"] in ids]


# --- superadmin only -------------------------------------------------------------------------

@pytest.mark.parametrize("url", [URL, EXPORT])
def test_anonymous_and_space_manager_are_refused(url):
    row = space("ovr-auth")
    manager = make_member(f"ovr-sm-{uuid.uuid4().hex[:6]}", row)
    from rest_framework.test import APIClient
    assert APIClient().get(url).status_code in (401, 403)
    assert authenticated_client(manager).get(url).status_code == 403


def test_superadmin_reads_the_overview():
    space("ovr-read")
    response = authenticated_client(superadmin()).get(URL, {"period": "this_month"})
    assert response.status_code == 200, response.data
    assert response.data["status"] == "ready"
    assert response["Cache-Control"] == "private, no-store"
    assert {item["key"] for item in response.data["blocks"]} >= {"people", "operations"}


def test_reports_links_use_current_module_state_with_cached_figures():
    stays_on = space("ovr-reports-on", modules=["reports"])
    switches_off = space("ovr-reports-off", modules=["reports"])
    window = resolve_window("this_month")
    snapshot = build_platform_overview(window, include_excluded=False)
    cache.set(cache_key(window, False), snapshot, 60)
    Makerspace.objects.filter(pk=switches_off.pk).update(
        enabled_modules=[key for key in switches_off.enabled_modules if key != "reports"],
    )

    response = authenticated_client(superadmin()).get(URL)

    assert response.status_code == 200
    assert stays_on.pk in response.data["reports_space_ids"]
    assert switches_off.pk not in response.data["reports_space_ids"]
    cached_reports = next(row for row in response.data["modules"] if row["key"] == "reports")
    assert switches_off.pk in cached_reports["space_ids"]


def test_unknown_parameter_and_bad_custom_period_are_400():
    client = authenticated_client(superadmin())
    assert client.get(URL, {"space": "1"}).status_code == 400
    assert client.get(URL, {"period": "custom", "start": "2026-02-10", "end": "2026-02-01"}).status_code == 400
    assert client.get(URL, {"period": "this_year", "start": "2026-01-01"}).status_code == 400
    assert client.get(URL, {"period": "fortnight"}).status_code == 400


# --- totals equal the per-space sums ------------------------------------------------------------

def test_every_summable_total_equals_the_sum_of_its_space_rows():
    first, second = space("ovr-sum-a"), space("ovr-sum-b")
    for _ in range(3):
        member(first)
    member(second)
    make_member(f"ovr-sm-{uuid.uuid4().hex[:6]}", second)
    data = overview()
    for item in data["blocks"]:
        for metric in item["metrics"]:
            if metric["unit"] == "percent":
                continue
            values = [row["values"][metric["key"]] for row in item["rows"] if row["values"] is not None]
            expected = round(sum(values), 1) if metric["unit"] == "hours" else sum(values)
            assert item["totals"][metric["key"]] == expected, (item["key"], metric["key"])
    people = {row["makerspace_id"]: row["values"] for row in block(data, "people")["rows"]}
    assert people[first.pk]["members"] == 3
    assert people[second.pk]["members"] == 1
    assert people[second.pk]["staff"] >= 1


# --- money per currency -------------------------------------------------------------------------

def test_money_is_grouped_per_currency_and_never_summed_across():
    first = space("ovr-money-a", features=["charges.enabled"])
    second = space("ovr-money-b", features=["charges.enabled"])
    payment(first, member(first), "10.00", "inr")
    payment(first, member(first), "5.50", "inr", status=Payment.Status.PAID_OFFLINE)
    payment(second, member(second), "7.00", "usd")
    money = overview()["money"]
    assert money is not None
    by_currency = {entry["currency"]: entry for entry in money["currencies"]}
    assert {"inr", "usd"} <= set(by_currency)
    inr, usd = by_currency["inr"], by_currency["usd"]
    inr_ours = [row for row in inr["rows"] if row["makerspace_id"] == first.pk]
    assert inr_ours and inr_ours[0]["charges"] == 2
    assert inr_ours[0]["amounts"]["charged"] == "15.50"
    assert inr_ours[0]["amounts"]["outstanding"] == "10.00"
    assert not [row for row in inr["rows"] if row["makerspace_id"] == second.pk]
    assert [row for row in usd["rows"] if row["makerspace_id"] == second.pk][0]["amounts"]["charged"] == "7.00"
    for entry in money["currencies"]:
        total = sum(Decimal(row["amounts"]["charged"]) for row in entry["rows"])
        assert Decimal(entry["totals"]["amounts"]["charged"]) == total


# --- module-off hiding --------------------------------------------------------------------------

def test_a_block_off_in_one_space_shows_off_there_and_adds_nothing():
    on = space("ovr-ev-on", modules=["events"])
    off = space("ovr-ev-off")
    without(off, "events")
    events = block(overview(), "events")
    assert events is not None
    rows = {row["makerspace_id"]: row["values"] for row in events["rows"]}
    assert rows[off.pk] is None
    assert rows[on.pk] is not None
    assert events["off_in"] >= 1


def test_a_block_off_everywhere_is_omitted_and_listed_in_hidden_blocks(monkeypatch):
    from dataclasses import replace

    from apps.operations import platform_overview as builder

    space("ovr-hidden")
    closed = replace(builder.MACHINES, gate=lambda _space: False)
    monkeypatch.setattr(builder, "BLOCKS", tuple(closed if item.key == "machines" else item for item in builder.BLOCKS))
    data = overview()
    assert block(data, "machines") is None
    hidden = {item["key"]: item for item in data["hidden_blocks"]}
    assert hidden["machines"]["on_in"] == 0
    assert hidden["machines"]["off_in"] == len(data["spaces"])


def test_hidden_block_contract_with_a_gate_that_is_off_everywhere():
    from dataclasses import replace

    from apps.operations import platform_overview as builder

    space("ovr-gate")
    window = resolve_window("this_month")
    closed = replace(builder.MACHINES, gate=lambda _space: False)
    built, off = builder.build_block(closed, list(builder.select_spaces(False)[0]), window, timezone.now())
    assert built is None
    assert off["key"] == "machines" and off["on_in"] == 0 and off["off_in"] >= 1


# --- excluded spaces ----------------------------------------------------------------------------

def test_archived_spaces_are_excluded_by_default_and_toggle_back_in():
    live = space("ovr-live")
    archived = space("ovr-arch")
    archived.archived_at = timezone.now() - timedelta(days=1)
    archived.save(update_fields=["archived_at"])
    default = overview()
    assert {row["id"] for row in ours(default, live, archived)} == {live.pk}
    assert default["excluded_count"] >= 1
    toggled = overview(include_excluded=True)
    rows = {row["id"]: row for row in ours(toggled, live, archived)}
    assert set(rows) == {live.pk, archived.pk}
    assert rows[archived.pk]["excluded_reason"] == "archived"
    assert rows[live.pk]["excluded_reason"] is None


def test_directory_hidden_spaces_are_excluded_by_default_and_toggle_back_in():
    """#183A gap 16: a space hidden from the central directory is left out by default, like an
    archived one, and the same toggle adds it back, still flagged as directory-hidden."""
    live = space("ovr-live-d")
    hidden = space("ovr-dir")
    hidden.hidden_from_central_directory = True
    hidden.save(update_fields=["hidden_from_central_directory"])
    default = overview()
    assert {row["id"] for row in ours(default, live, hidden)} == {live.pk}
    assert default["excluded_count"] >= 1
    people = block(default, "people")
    assert hidden.pk not in {row["makerspace_id"] for row in people["rows"]}
    toggled = overview(include_excluded=True)
    rows = {row["id"]: row for row in ours(toggled, live, hidden)}
    assert set(rows) == {live.pk, hidden.pk}
    assert rows[hidden.pk]["excluded_reason"] == "directory_hidden"
    assert rows[hidden.pk]["directory_hidden"] is True
    assert rows[live.pk]["excluded_reason"] is None


def test_archived_reason_wins_over_directory_hidden():
    row = space("ovr-arch-dir")
    row.hidden_from_central_directory = True
    row.archived_at = timezone.now() - timedelta(days=1)
    row.save(update_fields=["hidden_from_central_directory", "archived_at"])
    rows = ours(overview(include_excluded=True), row)
    assert rows[0]["excluded_reason"] == "archived"


def test_the_api_toggle_adds_directory_hidden_spaces_back():
    hidden = space("ovr-dir-api")
    hidden.hidden_from_central_directory = True
    hidden.save(update_fields=["hidden_from_central_directory"])
    client = authenticated_client(superadmin())
    default = client.get(URL, {"period": "all_time"})
    assert default.status_code == 200
    assert hidden.pk not in {row["id"] for row in default.data["spaces"]}
    toggled = client.get(URL, {"period": "all_time", "include_excluded": "true"})
    assert toggled.status_code == 200
    assert hidden.pk in {row["id"] for row in toggled.data["spaces"]}


# --- no PII -------------------------------------------------------------------------------------

def test_no_person_data_in_the_payload_or_the_csv():
    row = space("ovr-pii", features=["charges.enabled"])
    person = member(row, f"ovr-secret-{uuid.uuid4().hex[:6]}")
    person.first_name, person.last_name = "Zebulon", "Quixotic"
    person.save(update_fields=["first_name", "last_name"])
    payment(row, person, "3.00", "inr")
    client = authenticated_client(superadmin())
    body = json.dumps(client.get(URL, {"period": "all_time"}).data)
    csv_text = client.get(EXPORT, {"period": "all_time"}).content.decode()
    for needle in (person.username, person.email, "Zebulon", "Quixotic"):
        assert needle not in body
        assert needle not in csv_text


# --- export audit -------------------------------------------------------------------------------

def test_export_is_csv_and_audited():
    space("ovr-export")
    actor = superadmin()
    before = AuditLog.objects.filter(action="platform.overview_exported").count()
    response = authenticated_client(actor).get(EXPORT, {"period": "this_year", "include_excluded": "true"})
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    text = response.content.decode()
    assert text.startswith("# SpaceWorks platform overview period=this_year")
    assert "block,metric,label,unit,timing,scope,makerspace_id,makerspace,currency,value" in text
    rows = AuditLog.objects.filter(action="platform.overview_exported").order_by("-pk")
    assert rows.count() == before + 1
    entry = rows.first()
    assert entry.actor_id == actor.pk and entry.makerspace_id is None
    assert entry.meta["period"] == "this_year" and entry.meta["include_excluded"] is True


def test_a_read_does_not_write_an_audit_row():
    before = AuditLog.objects.filter(action="platform.overview_exported").count()
    authenticated_client(superadmin()).get(URL)
    assert AuditLog.objects.filter(action="platform.overview_exported").count() == before


# --- background computation ---------------------------------------------------------------------

def test_a_running_computation_answers_202_computing():
    window = resolve_window("this_month")
    cache.add(f"{cache_key(window, False)}:lock", 1, 60)
    response = authenticated_client(superadmin()).get(URL, {"period": "this_month"})
    assert response.status_code == 202
    assert response.data == {"status": "computing", "retry_after_seconds": 5}
    assert response["Retry-After"] == "5"
    export = authenticated_client(superadmin()).get(EXPORT, {"period": "this_month"})
    assert export.status_code == 202


def test_the_result_is_cached_until_refresh(monkeypatch):
    from apps.operations import platform_overview_cache

    client = authenticated_client(superadmin())
    assert client.get(URL, {"period": "all_time"}).status_code == 200
    calls = []
    real = platform_overview_cache.compute_and_store
    monkeypatch.setattr(platform_overview_cache, "compute_and_store",
                        lambda *args, **kwargs: calls.append(1) or real(*args, **kwargs))
    assert client.get(URL, {"period": "all_time"}).status_code == 200
    assert not calls
    assert client.get(URL, {"period": "all_time", "refresh": "true"}).status_code in (200, 202)
    assert calls  # refresh recomputes (inline under CELERY_TASK_ALWAYS_EAGER)
