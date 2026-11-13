"""Published release selection works with stdlib only and no installed updates app."""
import importlib.util
import json
from pathlib import Path

import pytest

HELPER = Path(__file__).resolve().parents[2] / "scripts/select-main-release.py"
spec = importlib.util.spec_from_file_location("release_selector", HELPER)
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


def release(run, published="2026-10-10T10:00:00Z", **changes):
    return {"tag_name": f"v0.9.0-main.{run}.aaaaaaaaaaaa", "published_at": published,
            "draft": False, "prerelease": False, **changes}


def test_newest_means_publication_order():
    data = [release(10), release(9, "2026-10-11T10:00:00Z")]
    assert selector.select_release(json.dumps(data)) == "0.9.0-main.9.aaaaaaaaaaaa"


@pytest.mark.parametrize("changes", [{"draft": True}, {"prerelease": True},
                                     {"published_at": None}, {"published_at": ""},
                                     {"tag_name": "v0.9.0"}, {"tag_name": "latest"}])
def test_ineligible_releases_cannot_select_images(changes):
    with pytest.raises(ValueError, match="No published"):
        selector.select_release(json.dumps([release(1, **changes)]))


def test_size_and_shape_are_bounded():
    with pytest.raises(ValueError, match="size limit"):
        selector.select_release("x" * (selector.MAX_RESPONSE_SIZE + 1))
    with pytest.raises(ValueError, match="release list"):
        selector.select_release("{}")


def test_pinned_tag_is_checked_separately_from_latest_list():
    version = "0.9.0-main.1.aaaaaaaaaaaa"
    data = release(1, html_url=f"https://github.com/Owner/Fork/releases/tag/v{version}")
    assert selector.select_release(json.dumps(data), version, "Owner/Fork") == version


@pytest.mark.parametrize("data", [None, [], {}, {"message": "Not Found"}, release(2),
                                  release(1, draft=True), release(1, prerelease=True),
                                  release(1, published_at=None),
                                  release(1, html_url="https://github.com/Other/Fork/releases/tag/v0.9.0-main.1.aaaaaaaaaaaa")])
def test_pin_refuses_missing_or_ineligible_metadata(data):
    with pytest.raises(ValueError):
        selector.select_release(json.dumps(data), "0.9.0-main.1.aaaaaaaaaaaa", "Owner/Fork")
