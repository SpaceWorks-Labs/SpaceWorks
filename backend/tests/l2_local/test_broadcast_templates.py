"""G6 templates and brand designs ride events.broadcast_templates (on and off)."""
import pytest
from rest_framework.exceptions import ValidationError

from apps.events.programme.broadcast_designs import DESIGNS, document
from apps.integrations.broadcasts_templates import EVENT_STARTER_TEMPLATES
from tests.events.collab_helpers import client_for
from tests.events.lane_d_helpers import fixture
from tests.l2_local.helpers import composer, off, on

pytestmark = pytest.mark.django_db


def test_thirteen_original_templates_use_only_known_placeholders():
    from apps.events.programme.broadcast_content import PLACEHOLDERS
    from apps.integrations.broadcasts_templates import validate_strings
    assert len(EVENT_STARTER_TEMPLATES) == 13
    for template in EVENT_STARTER_TEMPLATES:
        validate_strings(template["subject"], template["body"], PLACEHOLDERS)
        assert template["design"] in DESIGNS


def test_templates_route_is_404_while_off_and_listed_while_on(monkeypatch):
    space, actor, _member, event, _registration = fixture(monkeypatch)
    url = f"/api/v1/admin/events/{event.pk}/broadcast-templates/"
    assert client_for(actor).get(url).status_code == 404
    on(space, "events.broadcast_templates")
    response = client_for(actor).get(url)
    assert response.status_code == 200 and len(response.json()) == 13


def test_new_designs_need_the_switch_but_classic_never_does(monkeypatch):
    space, actor, _member, event, _registration = fixture(monkeypatch)
    off(space, "events.broadcast_templates")
    classic = composer(event, actor)
    assert classic.design == "classic"
    # Parity E-B7 (uniq_event_broadcast_open_draft): one open composer draft per author and event, so close the first.
    type(classic).objects.filter(pk=classic.pk).update(status="cancelled")
    with pytest.raises(ValidationError):
        composer(event, actor, "letter")
    on(space, "events.broadcast_templates")
    assert composer(event, actor, "letter").design == "letter"


@pytest.mark.parametrize("design", DESIGNS)
def test_every_design_renders_light_and_dark_with_escaped_content(design):
    html = document(design, fonts="", width=640, title_html="&lt;b&gt;", message_html="<p>x</p>",
                    links_html="", organization="<Org>", cover_url="")
    assert "prefers-color-scheme:dark" in html and "<Org>" not in html
