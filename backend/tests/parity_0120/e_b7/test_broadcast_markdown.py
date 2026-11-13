"""E-B7 broadcast markdown: richer, still data-only."""
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from apps.events.programme.broadcast_content import pack, render_content
from apps.events.programme.broadcast_markdown import markdown_html, plain_text, safe_url

CONTEXT = {"name": "Sam", "event_title": "Make", "event_date": "d", "event_location": "Lab",
           "ticket_url": "https://t.example.test/1", "event_url": "https://e.example.test/",
           "feedback_url": "https://f.example.test/", "schedule_url": "https://s.example.test/plan",
           "organization": "Org"}


def campaign_for(body):
    return SimpleNamespace(render_schema_version=2, design="classic", subject="Hi",
                           body=pack("Hi", body, ctas=[], design="classic"))


def test_headings_quotes_numbered_lists_and_links_render():
    body = ("# Welcome\n\n> A quote\n> second line\n\n1. First\n2. Second\n\n"
            "Read [the guide](https://example.test/guide) or [write us](mailto:hi@example.test).")
    html = markdown_html(body)
    assert "Welcome</h2>" in html
    assert "<blockquote" in html and "A quote<br>second line" in html
    assert "<ol><li>First</li><li>Second</li></ol>" in html
    assert '<a rel="noopener noreferrer" href="https://example.test/guide">the guide</a>' in html
    assert 'href="mailto:hi@example.test"' in html


@pytest.mark.parametrize("body", [
    "[x](javascript:alert(1))", "[x](http://example.test)", "[x](https://user:pw@example.test/)",
    "[x](https://example.test/?token=abc)", "[x](https://example.test/invite/abc)",
    "[x](data:text/html;base64,AAAA)", "![img](https://example.test/a.png)", "<b>bold</b>",
    "[x](mailto:not-an-address)", "[x]( https://example.test)", "[x]({{ ticket_token }})",
])
def test_unsafe_links_and_markup_refuse(body):
    with pytest.raises(ValidationError):
        pack("Notice", body, ctas=[], design="classic")


def test_url_placeholder_links_are_allowed_and_resolved():
    rendered = render_content(campaign_for("[Schedule]({{ schedule_url }})"), CONTEXT, preview=True)
    assert 'href="https://s.example.test/plan"' in rendered["html_body"]
    assert "Schedule (https://s.example.test/plan)" in rendered["text_body"]


def test_names_cannot_smuggle_links_into_the_body():
    context = {**CONTEXT, "name": "[Pay](https://evil.example.test/)"}
    rendered = render_content(campaign_for("Hello {{ name }}"), context, preview=True)
    assert 'href="https://evil.example.test/' not in rendered["html_body"]


def test_plain_text_projection_and_safe_url():
    assert plain_text("# Title\n[A](https://example.test/x)") == "Title\nA (https://example.test/x)"
    assert safe_url("https://example.test/x") and safe_url("mailto:a@example.test")
    assert safe_url("javascript:alert(1)") is None and safe_url("http://example.test") is None
