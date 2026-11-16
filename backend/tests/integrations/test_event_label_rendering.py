"""Notification prose shows the lifecycle event in words; the machine key stays for comparisons."""
from apps.integrations.email_templates import render_preview
from apps.integrations.email_templates_registry import iter_entries
from apps.integrations.event_labels import event_label, with_event_label


def test_event_label_turns_the_key_into_words():
    assert event_label("payment_due_today") == "payment due today"
    assert event_label(None) == ""
    assert with_event_label({"event_name": "restored"})["event_label"] == "restored"
    assert with_event_label({"event_name": "x", "event_label": "kept"})["event_label"] == "kept"
    assert "event_label" not in with_event_label({"other": 1})


def test_rendered_text_uses_words_but_comparisons_still_see_the_key():
    out = render_preview("payments", "requester", "payment_due_today",
                         "{{ event_label }}", "{% if event_name == 'payment_due_today' %}due:{{ event_label }}{% endif %}", "")
    assert out["subject"] == "payment due today"
    assert out["text_body"] == "due:payment due today"


def test_default_templates_never_print_the_raw_event_key():
    for (stream, audience, key_name), entry in iter_entries():
        context = dict(entry.sample_context or {})
        key = context.get("event_name")
        if not key or "_" not in str(key):
            continue
        out = render_preview(stream, audience, key_name, entry.default_subject,
                             entry.default_text, entry.default_html)
        assert str(key) not in out["text_body"], (stream, audience, key_name)
