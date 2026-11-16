from unittest.mock import Mock

import pytest

from apps.events.registration_form_adapter import validate_registration_form
from apps.events.programme.commands import ProgrammeUnavailable


def test_v2_registration_fails_before_validation_when_canonical_storage_is_not_mapped(monkeypatch):
    monkeypatch.setattr("django.apps.apps.get_model", lambda label: type("UnmappedRegistration", (), {}))
    validator = Mock()
    with pytest.raises(ProgrammeUnavailable) as caught:
        validate_registration_form({"answers": {}}, schema={"schema_version": 2}, subject=object(), validator=validator)
    assert "private_answer_storage_unavailable" in str(caught.value.detail)
    validator.assert_not_called()
