"""Startup composition must install value adapters without DB or network work."""

import inspect

from apps.events.contracts import registration
from apps.events.judging.provider_runtime import JudgingProviders
from apps.events.judging.ports import ProgrammePorts


def test_judging_installed_adapter_implements_every_port_method():
    required = {name for name, value in vars(ProgrammePorts).items()
                if not name.startswith("_") and inspect.isfunction(value)}
    assert required <= {name for name in dir(JudgingProviders) if callable(getattr(JudgingProviders, name))}


def test_actual_startup_composition_is_query_free_without_db_access(monkeypatch):
    from apps.events.judging import ports, provider_notices
    from apps.integrations.notification_sources import SOURCES
    from apps.events.profile_photos import policy
    from apps.events.programme import providers
    from apps.accounts.saved_details import fields, prefill
    from apps.events.submissions import api_runtime
    from apps.events.certificates import subjects
    from apps.events.programme_sections import providers as sections
    from apps.events.contracts import pages_registration
    for module, name, value in (
        (ports, "_installed", None), (policy, "_subjects", {}), (policy, "_public_surfaces", {}),
        (providers, "_forms", {}), (providers, "_readiness", {}), (providers, "_respondents", None),
        (providers, "_answers", None),
        (fields, "_provider", None), (prefill, "_provider", None), (api_runtime, "_runtime", None),
        (sections, "_pages", None), (pages_registration, "_providers", {}),
        (subjects, "_role_eligibility", None), (subjects, "_award_eligibility", None),
    ):
        monkeypatch.setattr(module, name, value)
    monkeypatch.delitem(SOURCES, provider_notices.SOURCE, raising=False)
    # No django_db marker: pytest-django refuses accidental ORM during install.
    registration.install()
    assert isinstance(ports.runtime(), JudgingProviders)
    assert set(providers._forms) == {"application", "volunteer", "mentor", "round", "track"}
    assert set(policy._public_surfaces) == {"team", "mentor", "judge"}
    assert api_runtime.runtime().saved_resume_provider is not None
    # Undo the registry insertion too, so this test does not leak test order state.
    SOURCES.pop(provider_notices.SOURCE)
