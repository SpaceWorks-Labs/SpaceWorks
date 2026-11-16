"""#183B(g): every installed first-party app is either separable or core, with a reason."""
from django.apps import apps

from apps.separability.tombstones import CORE_APPS, SEPARABLE_APPS


def test_every_first_party_app_is_classified_once():
    labels = {cfg.label for cfg in apps.get_app_configs() if cfg.name.startswith("apps.")}
    assert labels - SEPARABLE_APPS - set(CORE_APPS) == set()
    assert SEPARABLE_APPS & set(CORE_APPS) == set()
    assert set(CORE_APPS) <= labels
    assert all(reason.strip() for reason in CORE_APPS.values())
