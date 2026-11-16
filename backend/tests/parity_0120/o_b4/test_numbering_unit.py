"""O-B4 numbering engine: token rendering and validation (no database)."""
import pytest
from rest_framework.exceptions import ValidationError

from apps.card_designs import numbering


def test_render_fills_every_token_and_pads_the_width():
    text = numbering.render("{PREFIX}-{YYYY}-{SEQ:4}-{MEMBER:3}-{U1}", prefix="TNK", seq=42, member=7, year=2026)
    assert text == "TNK-2026-0042-007-NA"


def test_two_digit_year_and_unit_codes():
    assert numbering.render("{YY}{UNIT}{SEQ}", seq=5, year=2026, units=("N", "KOCHI")) == "26KOCHI5"


def test_validate_requires_exactly_one_seq_and_uppercases():
    assert numbering.validate("tnk", "{PREFIX}-{SEQ:4}") == ("TNK", "{PREFIX}-{SEQ:4}")
    with pytest.raises(ValidationError):
        numbering.validate("", "ABC")
    with pytest.raises(ValidationError):
        numbering.validate("", "{SEQ}{SEQ}")


def test_validate_refuses_bad_prefix_width_literal_and_length():
    for prefix, pattern in (("X", "{SEQ}"), ("", "{YYYY:4}{SEQ}"), ("", "{SEQ}#"), ("", "A" * 30 + "{SEQ:6}"),
                            ("", "{PREFIX}{SEQ}")):
        with pytest.raises(ValidationError):
            numbering.validate(prefix, pattern)


def test_empty_pattern_means_no_scheme():
    assert numbering.validate("", "") == ("", "")
    assert numbering.preview("", "") == []


def test_year_token_resets_the_counter_only_for_year_patterns():
    assert numbering.has_year("{YYYY}-{SEQ}") and not numbering.has_year("{SEQ}")
