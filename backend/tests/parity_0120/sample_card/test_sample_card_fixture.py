"""The sample staff card on the sign-in screens is generated, not hand-copied: the checked-in fixture must equal
what scripts/export_sample_card.py produces from the real default templates. Regenerate with that script."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "frontend" / "src" / "features" / "auth" / "sampleCard.generated.json"


def _script():
    spec = importlib.util.spec_from_file_location("export_sample_card", ROOT / "scripts" / "export_sample_card.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixture_matches_generator_output():
    expected = json.dumps(_script().sample_document(), indent=1, sort_keys=True) + "\n"
    assert FIXTURE.read_text(encoding="utf-8") == expected, "run: python scripts/export_sample_card.py"


def test_staff_numbering_default_is_what_the_sample_shows():
    # Decision 306 addendum 2: the sample uses the owner's scheme TNK + "{PREFIX}-STF-{SEQ:4}" (TNK-STF-0007), rendered
    # by the same engine grammar; the real staff default scheme is unchanged.
    from apps.card_designs import numbering, staff_card_numbering
    assert staff_card_numbering.DEFAULT == ("STF", "{PREFIX}-{SEQ:4}")
    numbering.validate("TNK", "{PREFIX}-STF-{SEQ:4}")
    assert numbering.render("{PREFIX}-STF-{SEQ:4}", prefix="TNK", seq=7) == "TNK-STF-0007"
