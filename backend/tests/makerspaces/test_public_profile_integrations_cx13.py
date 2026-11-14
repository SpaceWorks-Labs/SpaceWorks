"""549 / R1: sitemap membership privacy, crawler dispatch and accurate notices."""
from pathlib import Path
import re
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest
from rest_framework.test import APIClient

from apps.makerspaces.models import AccountProfile, MakerspaceMembership, MinorProfile
from tests.makerspaces.test_public_profile_cx13 import add_membership, person

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("scope", ["host", "origin"])
@pytest.mark.parametrize("hidden_field,value", [("hidden_from_central_directory", True),
                                                ("enabled_modules", [])])
def test_tenant_sitemap_omits_hidden_or_private_associations_and_restores(person, scope, hidden_field, value):
    space, membership = add_membership(person, frontend_domain="profile.example.test", frontend_domain_status="verified")
    headers = {"HTTP_HOST": space.frontend_domain} if scope == "host" else {"HTTP_ORIGIN": "https://profile.example.test"}

    def urls():
        response = APIClient().get("/sitemap.xml", **headers)
        assert response.status_code == 200
        return {node.text for node in ElementTree.fromstring(response.content).iter()
                if node.tag.endswith("}loc")}

    assert urls() == {"http://testserver/@cx13.maker"}
    original = getattr(space, hidden_field)
    setattr(space, hidden_field, value)
    space.save(update_fields=[hidden_field])
    assert urls() == set()
    assert MakerspaceMembership.objects.get(pk=membership.pk).status == "active"
    setattr(space, hidden_field, original)
    space.save(update_fields=[hidden_field])
    assert urls() == {"http://testserver/@cx13.maker"}


@pytest.mark.parametrize("standing", ["restricted", "suspended", "inactive", "minor"])
def test_sitemap_keeps_account_standing_and_minor_indexing_exclusions(person, standing):
    space, _ = add_membership(person)
    if standing == "minor":
        MinorProfile.objects.create(makerspace=space, user=person, declared_under_age=True)
    elif standing == "inactive":
        type(person).objects.filter(pk=person.pk).update(is_active=False)
    else:
        type(person).objects.filter(pk=person.pk).update(access_status=standing)
    response = APIClient().get("/sitemap.xml")
    assert response.status_code == 200
    assert {node.text for node in ElementTree.fromstring(response.content).iter()
            if node.tag.endswith("}loc")} == set()


@pytest.mark.parametrize("filename", ["Caddyfile", "Caddyfile.saas", "Caddyfile.saas-install"])
def test_every_caddy_config_maps_at_handle_and_keeps_legacy_alias(filename):
    source = (ROOT / "deploy" / filename).read_text(encoding="utf-8")
    expression = re.search(r"path_regexp member_profile_card (.+)", source).group(1)
    assert re.fullmatch(expression, "/@cx13.maker").group(1) == "cx13.maker"
    assert "rewrite * /share/profiles/{re.member_profile_card.1}/" in source
    for path in ("/@ab", "/@bad!", "/@.maker", "/@maker-", "/@" + "a" * 31, "/@maker/extra"):
        assert re.fullmatch(expression, path) is None
    legacy = re.search(r"path_regexp profile_card (.+)", source).group(1)
    assert re.fullmatch(legacy, "/cx13.maker").group(1) == "cx13.maker"
    target = "profiles" if filename == "Caddyfile" else "pages"
    assert f"rewrite * /share/{target}/{{re.profile_card.1}}/" in source


def test_static_crawler_mapping_keeps_shared_alias_and_refuses_malformed_names():
    source = (ROOT / "deploy/static/shared/routes.mjs").read_text(encoding="utf-8")
    crawler = re.search(r"if \(/(.+)/i\.test\(userAgent\)\) \{", source)
    assert crawler is not None
    assert re.search(crawler.group(1), "Twitterbot", re.IGNORECASE) is not None
    rules = []
    for name, condition, flags in (
        ("member", "member", "i"),
        ("handle", r"handle && !RESERVED\.has\(handle\[1\]\)", ""),
    ):
        # Read the shipped regex and rewrite together, rather than copying their values.
        rule = re.search(
            rf"const {name} = path\.match\(/(.+)/([a-z]*)\);\s*"
            rf"if \({condition}\) return \{{ kind: 'proxy', path: `([^`]+)` \}};",
            source,
        )
        assert rule is not None
        assert rule.group(2) == flags
        assert crawler.start() < rule.start() < source.rindex("\n  }\n  return { kind: 'asset' };")
        rules.append((name, re.compile(rule.group(1), re.IGNORECASE if flags == "i" else 0), rule.group(3)))

    def target(path):
        for name, expression, template in rules:
            match = expression.fullmatch(path)
            if match:
                return {"kind": "proxy", "path": template.replace("${" + name + "[1]}", match.group(1))}
        return {"kind": "asset"}

    paths = ["/@cx13.maker", "/cx13.maker", "/@ab", "/@bad!", "/@.maker", "/@maker-", "/@" + "a" * 31]
    assert [target(path) for path in paths] == [
        {"kind": "proxy", "path": "/share/profiles/cx13.maker/"},
        {"kind": "proxy", "path": "/share/pages/cx13.maker/"},
        *[{"kind": "asset"}] * 5,
    ]


def test_crawler_target_keeps_exact_minor_share_refusal(person):
    space, _ = add_membership(person)
    MinorProfile.objects.create(makerspace=space, user=person, declared_under_age=True)
    response = APIClient().get("/share/profiles/cx13.maker/", HTTP_USER_AGENT="Twitterbot")
    assert response.status_code == 404
    assert response.data["code"] == "not_found"


@pytest.mark.parametrize("reconfirm", [False, True])
def test_open_notice_has_exact_current_wording_and_owner_recipient(person, monkeypatch, reconfirm):
    from apps.makerspaces import notifications_profile_open as notices
    space, _ = add_membership(person)
    AccountProfile.objects.filter(user=person).update(is_visible=True, public_reconfirm_pending=reconfirm)
    profile = AccountProfile.objects.get(user=person)
    captured = []

    def fanout(**kwargs):
        captured.append(kwargs)
        return object()

    monkeypatch.setattr(notices, "fanout", fanout)
    notices.notify_opened.__wrapped__(profile, space)
    assert len(captured) == 1
    intent = captured[0]
    assert intent["owner"].pk == person.pk
    assert intent["space"].pk == space.pk
    assert intent["staff"] is None
    assert intent["source"] == profile.pk
    assert intent["version"] == notices.revision(profile.pk, "open-notice-v1")
    assert intent["own"]() == {
        "subject": "Your public profile is available",
        "text": "Your public profile is always available when you have a handle. It shows your name, "
                "avatar, chosen bio and published projects, and eligible public memberships. "
                "You can edit your bio and choose which projects to publish in your profile settings. "
                "Minors and restricted or suspended accounts show only their name and avatar.",
        "link": "/m/cx13-lab/member",
    }
    envelope = SimpleNamespace(source_id=profile.pk, audience="requester", recipient_id=person.pk,
                               revision=intent["version"])
    assert notices.eligible(envelope) is True
    envelope.recipient_id += 1
    assert notices.eligible(envelope) is False
    profile.refresh_from_db()
    assert profile.public_reconfirm_pending is reconfirm


def test_profile_audit_presentation_paths_match_exact_emitted_metadata():
    from apps.audit.presentation_catalog_accounts import ENTRIES
    entry = next(row for row in ENTRIES if row.action == "member.profile_updated")
    assert entry.permitted_meta_paths == (
        "attended_events_changed", "attended_events_shown", "certifications_shown", "fields",
        "projects_after", "projects_before", "sections_changed",
    )
