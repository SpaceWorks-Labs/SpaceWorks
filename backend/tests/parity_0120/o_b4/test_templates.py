"""O-B4: the seven added card looks are valid v2 documents in both themes, contrast included."""
import pytest

from apps.card_designs.default_templates import LABELS, ORG_LOOKS, REVISION, THEMES, TEMPLATES, build
from apps.card_designs.layout import normalize_document


def test_seven_looks_were_added_and_the_revision_moved():
    assert set(ORG_LOOKS) == {"aurora", "kasavu", "ribbon", "confetti", "midnight", "sunrise", "standard_portrait"}
    assert len(LABELS) == 13 and REVISION >= 3


@pytest.mark.parametrize("key", sorted(TEMPLATES))
@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("domain", ["member_cards", "id_programme"])
def test_every_look_validates_with_contrast(key, theme, domain):
    normalize_document(build(key, domain, theme), check_contrast=True)


def test_standard_portrait_is_a_portrait_cr80_and_the_error_names_no_count():
    from rest_framework.exceptions import ValidationError
    assert build("standard_portrait", "member_cards")["stock"] == "cr80-portrait"
    with pytest.raises(ValidationError) as refused:
        build("nope", "member_cards")
    assert "six" not in str(refused.value.detail)
