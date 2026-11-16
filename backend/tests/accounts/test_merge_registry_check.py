"""accounts.E003: every reference to accounts.User has an account-merge disposition."""

import pytest

from apps.accounts import merge_registry
from apps.accounts.checks import check_merge_registry
from apps.accounts.merge_registry_types import compose, KEEP_ON_SHELL, REPOINT


def test_the_shipped_registry_is_complete_and_exact():
    assert merge_registry.problems() == {
        "unclassified_relations": [], "unclassified_columns": [],
        "stale_relations": [], "stale_columns": [],
    }
    assert check_merge_registry() == []


def test_named_dispositions_from_the_brief():
    d = merge_registry.disposition_for
    assert d("audit.AuditLog", "actor") == KEEP_ON_SHELL
    assert d("accounts.UserMFA", "user") == KEEP_ON_SHELL
    assert d("accounts.PlatformPiiAccessGrant", "actor") == KEEP_ON_SHELL
    assert d("makerspaces.MakerspaceSecurityLock", "locked_by") == KEEP_ON_SHELL
    assert d("backup.MakerspaceRestoreOperation", "requested_by") == REPOINT
    assert d("makerspaces.MakerspaceMembership", "user") == merge_registry.UNIQUE_RESOLVE
    assert d("encryption.PiiGlobalWriteFence", "actor_id") == KEEP_ON_SHELL
    assert d("machines.ServiceRequestFile", "owner_user_id") == REPOINT


def test_unclassified_relation_and_unlisted_user_id_column_fail(monkeypatch):
    relation = ("events.Event", "created_by")
    column = ("encryption.PiiGlobalWriteFence", "actor_id")
    monkeypatch.setattr(merge_registry, "USER_REFERENCES",
                        {key: value for key, value in merge_registry.USER_REFERENCES.items() if key != relation})
    monkeypatch.setattr(merge_registry, "USER_ID_COLUMNS",
                        {key: value for key, value in merge_registry.USER_ID_COLUMNS.items() if key != column})
    errors = check_merge_registry()
    assert {error.id for error in errors} == {"accounts.E003"}
    messages = " ".join(error.msg for error in errors)
    assert "events.Event.created_by" in messages and "encryption.PiiGlobalWriteFence.actor_id" in messages


def test_stale_rows_fail(monkeypatch):
    monkeypatch.setattr(merge_registry, "USER_REFERENCES",
                        {**merge_registry.USER_REFERENCES, ("events.Event", "ghost"): REPOINT})
    assert any("stale relations events.Event.ghost" in error.msg for error in check_merge_registry())


def test_fragments_refuse_duplicates_and_missing_reasons():
    with pytest.raises(ValueError):
        compose(((REPOINT, "a.B", "x", "r"),), ((KEEP_ON_SHELL, "a.B", "x", "r"),))
    with pytest.raises(ValueError):
        compose(((REPOINT, "a.B", "x", " "),))
