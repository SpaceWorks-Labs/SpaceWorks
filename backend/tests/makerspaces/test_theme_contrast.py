import re
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.admin_api.serializers_makerspaces import MakerspaceSerializer
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership, default_theme_config
from apps.makerspaces.platform import bootstrap_payload
from apps.makerspaces.theme_contrast import BODY_TEXT, FIXED_INKS, PRODUCT_FILL, SURFACES, contrast, contrast_failures, derive_palette
from apps.makerspaces.theme_validation import validate_theme_config
from tests.return_helpers import authenticated_client, make_member


def test_wcag_srgb_contrast_math():
    assert contrast((0, 0, 0), (255, 255, 255)) == 21
    assert contrast((255, 255, 255), (0, 0, 0)) == 21
    assert contrast((100, 100, 100), (100, 100, 100)) == 1
    assert contrast((117, 117, 117), (255, 255, 255)) == pytest.approx(4.6075, abs=.0001)


@pytest.mark.parametrize("primary", ["#000", "#fff", "#f3c3dd", "#004400", "#abc"])
def test_custom_palette_passes_every_text_and_ui_pair_in_both_modes(primary):
    theme = {"primary_color": primary, "accent_color": "#5a1633"}
    assert validate_theme_config(theme) == theme
    assert contrast_failures(theme) == []


def test_dark_derivation_matches_frontend_golden_values():
    theme = {"primary_color": "#f3c3dd", "accent_color": "#5a1633"}
    light, dark = derive_palette(theme, "light"), derive_palette(theme, "dark")
    assert light["fill"] == dark["fill"] == (243, 195, 221)
    assert light["foreground"] == dark["foreground"] == (20, 44, 42)
    assert light["ink"] == (90, 22, 51)
    assert dark["ink"] == (174, 135, 143)
    palette = derive_palette({"primary_color": "#004400"}, "light")
    assert palette["hover"] == (26, 86, 23)
    assert palette["active"] == (51, 103, 46)
    assert palette["foreground"] == (255, 244, 232)


def test_midgrey_stays_accepted_and_derives_accessible_opaque_tokens():
    theme = {"primary_color": "#777"}
    assert validate_theme_config(theme) == theme
    for mode in ("light", "dark"):
        palette = derive_palette(theme, mode)
        assert palette["foreground"] == (0, 0, 0)
        assert all(ratio >= minimum for _pair, ratio, minimum in palette["pairs"])
        assert all(contrast(ink, palette["soft"]) >= 4.5 for ink in (*BODY_TEXT[mode], *FIXED_INKS[mode]))


def test_serializer_and_control_model_refuse_malformed_palette():
    theme = {"primary_color": "#777;display:none"}
    serializer = MakerspaceSerializer(data={"theme_config": theme}, partial=True)
    assert not serializer.is_valid()
    assert "theme_config" in serializer.errors
    space = Makerspace(name="Theme", slug="theme", theme_config=theme)
    with pytest.raises(ValidationError) as caught:
        space.clean()
    assert "theme_config" in caught.value.message_dict


def test_blank_defaults_use_product_palette_and_meet_aa():
    theme = default_theme_config()
    assert theme["primary_color"] == theme["accent_color"] == ""
    assert validate_theme_config(theme) == theme


def test_validation_surfaces_match_rendered_css_and_frontend_contract():
    frontend = Path(__file__).resolve().parents[3] / "frontend" / "src"
    if not frontend.exists():
        pytest.skip("Frontend source mount unavailable")
    css = re.sub(r"/\*.*?\*/", "", (frontend / "index.css").read_text(encoding="utf-8"), flags=re.S)
    ts = (frontend / "lib" / "brandColours.ts").read_text(encoding="utf-8")
    contracts = (
        ("BRAND_SURFACES", SURFACES, ("bg", "surface", "panel", "hover")),
        ("BODY_TEXT", BODY_TEXT, ("ink", "muted")),
        ("FIXED_INKS", FIXED_INKS, ("accent-ink", "success-ink", "warn-ink", "info-ink", "danger")),
    )
    for mode in ("light", "dark"):
        selector = r":root\s*\{" if mode == "light" else r":root\.dark(?:\s*,\s*\.sw-island-dark)?\s*\{"
        match = re.search(selector, css)
        assert match
        block = css[match.end():css.index("}", match.end())]
        for constant, values, names in contracts:
            for name, expected in zip(names, values[mode], strict=True):
                channels = re.search(rf"--color-{name}:\s*([\d\s]+);", block)
                assert channels
                assert tuple(map(int, channels.group(1).split())) == expected
            source = ts.split(f"export const {constant}:", 1)[1].split("};", 1)[0]
            source_line = next(line for line in source.splitlines() if line.strip().startswith(f"{mode}:"))
            assert tuple(map(int, re.findall(r"\d+", source_line))) == tuple(channel for color in values[mode] for channel in color)
        assert f"--color-brand: {' '.join(map(str, PRODUCT_FILL[mode]))};" in block
        for token, color in (("brand-soft", derive_palette({}, mode)["soft"]),):
            assert f"--color-{token}: {' '.join(map(str, color))};" in block


def test_opaque_soft_derivation_protects_normal_and_muted_text():
    palette = derive_palette({"primary_color": "#fff"}, "dark")
    assert palette["soft"] == (48, 48, 48)
    assert all(contrast(text, palette["soft"]) >= 4.5 for text in BODY_TEXT["dark"])


@pytest.mark.django_db
def test_malformed_theme_patch_400_does_not_write_or_audit():
    actor = User.objects.create_superuser(username="contrast-root", password="strong-password")
    space = Makerspace.objects.create(name="Contrast", slug="contrast")
    before = space.theme_config
    client = APIClient()
    client.force_authenticate(actor)
    response = client.patch(f"/api/v1/admin/makerspaces/{space.pk}", {
        "theme_config": {"primary_color": "#777;", "accent_color": "#5a1633"},
    }, format="json")
    assert response.status_code == 400
    assert "theme_config" in response.data
    space.refresh_from_db()
    assert space.theme_config == before
    assert not AuditLog.objects.filter(makerspace=space, action="makerspace.updated").exists()


@pytest.mark.django_db
def test_dark_brand_fill_is_accepted_and_audited():
    actor = User.objects.create_superuser(username="dark-brand-root", password="strong-password")
    space = Makerspace.objects.create(name="Dark Brand", slug="dark-brand")
    client = APIClient()
    client.force_authenticate(actor)
    response = client.patch(f"/api/v1/admin/makerspaces/{space.pk}", {
        "theme_config": {"primary_color": "#004400", "accent_color": "#5a1633"},
    }, format="json")
    assert response.status_code == 200
    space.refresh_from_db()
    assert space.theme_config["primary_color"] == "#004400"
    entry = AuditLog.objects.get(makerspace=space, action="makerspace.updated")
    assert entry.actor == actor
    assert entry.meta == {"fields": ["theme_config"]}


@pytest.mark.django_db
@pytest.mark.parametrize("stored", [[], "malformed", {"primary_color": "red"}, {"primary_color": "#777;"}])
def test_bootstrap_falls_back_for_invalid_restored_theme(stored):
    space = Makerspace.objects.create(name="Legacy Brand", slug="legacy-brand")
    Makerspace.objects.filter(pk=space.pk).update(theme_config=stored)
    space.refresh_from_db()
    assert bootstrap_payload(space)["theme"] == default_theme_config()


@pytest.mark.django_db
def test_bootstrap_colour_fallback_preserves_valid_mode_and_logo_without_writing():
    stored = {"mode": "dark", "primary_color": "#777;", "accent_color": "#000",
              "logo_url": "https://example.com/legacy-logo.png"}
    space = Makerspace.objects.create(name="Legacy Logo", slug="legacy-logo", theme_config=stored)
    payload = bootstrap_payload(space)
    assert payload["theme"] == {**default_theme_config(), "mode": "dark", "logo_url": stored["logo_url"]}
    assert payload["makerspace"]["logo_url"] == stored["logo_url"]
    space.refresh_from_db()
    assert space.theme_config == stored
    assert not AuditLog.objects.filter(makerspace=space, action="makerspace.updated").exists()


@pytest.mark.django_db
def test_space_manager_can_update_only_their_own_theme_and_audits_the_actor():
    own = Makerspace.objects.create(name="Own Theme", slug="own-theme")
    other = Makerspace.objects.create(name="Other Theme", slug="other-theme")
    manager = make_member("theme-manager", own, role=User.Role.REQUESTER)
    client = authenticated_client(manager)
    theme = {"primary_color": "#004400", "accent_color": "#fff"}
    before = other.theme_config
    assert client.patch(f"/api/v1/admin/makerspaces/{other.pk}", {"theme_config": theme}, format="json").status_code == 404
    assert client.patch(f"/api/v1/admin/makerspaces/{own.pk}", {"theme_config": theme}, format="json").status_code == 200
    other.refresh_from_db()
    own.refresh_from_db()
    assert other.theme_config == before
    assert own.theme_config == theme
    assert not AuditLog.objects.filter(makerspace=other, action="makerspace.updated").exists()
    entry = AuditLog.objects.get(makerspace=own, action="makerspace.updated")
    assert entry.actor == manager
    assert entry.meta == {"fields": ["theme_config"]}


@pytest.mark.django_db
def test_inventory_manager_cannot_update_a_theme():
    space = Makerspace.objects.create(name="Staff Theme", slug="staff-theme")
    staff = make_member("theme-inventory", space, membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER, role=User.Role.REQUESTER)
    before = space.theme_config
    response = authenticated_client(staff).patch(f"/api/v1/admin/makerspaces/{space.pk}", {"theme_config": {"primary_color": "#fff"}}, format="json")
    assert response.status_code == 404
    space.refresh_from_db()
    assert space.theme_config == before
    assert not AuditLog.objects.filter(makerspace=space, action="makerspace.updated").exists()


def test_links_and_semantic_inks_remain_readable_on_opaque_member_cards():
    from apps.makerspaces.theme_contrast import FIXED_SOFTS

    for mode in ("light", "dark"):
        palette = derive_palette({"primary_color": "#f3c3dd", "accent_color": "#5a1633"}, mode)
        for background in (palette["soft"], *FIXED_SOFTS[mode]):
            assert contrast(palette["ink"], background) >= 4.5
            assert all(contrast(ink, background) >= 4.5 for ink in FIXED_INKS[mode])


def test_member_directory_uses_opaque_soft_cards():
    frontend = Path(__file__).resolve().parents[3] / "frontend" / "src"
    if not frontend.exists():
        pytest.skip("Frontend source mount unavailable")
    directory = (frontend / "features" / "members" / "MemberDirectory.tsx").read_text(encoding="utf-8")
    assert '"bg-brand-soft"' in directory
    assert '"bg-accent-soft"' in directory
    assert 'className="desk-panel mt-2 border-brand p-3"' in directory
    assert not re.search(r"(?:bg|text)-(?:brand|accent|secondary)/\d", directory)
