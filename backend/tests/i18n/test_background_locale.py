"""Non-request output renders inside a scoped override that restores the prior locale."""
from unittest import mock

from django.utils import translation

from config import locale_resolution as lr


class _User:
    def __init__(self, code):
        self.preferred_locale = code


def test_one_locale_never_loads_the_recipient():
    loader = mock.Mock()
    assert lr.locale_for(user=loader) == "en"
    loader.assert_not_called()


def test_two_locales_follow_recipient_then_makerspace():
    with mock.patch.object(lr, "supported_codes", return_value=("en", "xx")), \
            mock.patch("config.locale_resolution.canonicalize", side_effect=lambda v: v if v in ("en", "xx") else None):
        assert lr.locale_for(user=lambda: _User("xx")) == "xx"
        assert lr.locale_for(user=_User(None)) == "en"


def test_override_restores_previous_language():
    translation.activate("en")
    with lr.override_for(user=None, makerspace=None) as code:
        assert code == "en"
    assert translation.get_language() == "en"
    translation.deactivate()


def test_sequential_tasks_do_not_leak():
    for _ in range(3):
        with lr.override_for():
            assert translation.get_language() == "en"
