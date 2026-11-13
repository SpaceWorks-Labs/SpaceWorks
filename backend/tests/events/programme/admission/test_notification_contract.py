import pytest
from apps.events.hackathons.admission_manifest import NOTICE_KINDS
from apps.events.hackathons.admission_notifications import MESSAGES, render_notice


def test_every_work_item_kind_has_a_minimal_personal_template():
    assert set(MESSAGES) == set(NOTICE_KINDS)
    for kind in NOTICE_KINDS:
        value = render_notice(kind=kind, application_url="/events/sample/application")
        assert set(value) == {"title", "body", "action_label", "action_url"}
        assert value["title"] and value["body"]


@pytest.mark.parametrize("url", ["https://outside.test", "//outside.test", "javascript:alert(1)"])
def test_notice_links_cannot_be_external(url):
    with pytest.raises(ValueError):
        render_notice(kind="application_offered", application_url=url)
