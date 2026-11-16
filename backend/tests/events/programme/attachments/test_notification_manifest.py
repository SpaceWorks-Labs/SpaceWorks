import pytest
from apps.events.programme.notification_manifest import register_programme_sources, missing_programme_sources
from apps.integrations.notification_sources import NotificationSource, SOURCES


def test_missing_domain_source_never_gains_a_permissive_default():
    assert "events.mentor_help" in missing_programme_sources([])
    with pytest.raises(ValueError):
        register_programme_sources([("events.unknown", NotificationSource(lambda envelope: True))])


def test_manifest_installs_original_predicate_without_queries(monkeypatch):
    monkeypatch.delitem(SOURCES, "events.mentor_help", raising=False)
    predicate = lambda envelope: False
    source = NotificationSource(predicate)
    monkeypatch.setitem(SOURCES, "events.mentor_help", source)
    assert register_programme_sources([("events.mentor_help", source)]) == frozenset({"events.mentor_help"})
    assert SOURCES["events.mentor_help"].eligible is predicate
