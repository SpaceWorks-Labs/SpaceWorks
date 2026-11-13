"""Write backend/apps/card_designs/fixtures/studio_plan_cases.json and studio_compat_cases.json.

The golden fixtures the Card Studio TS twin is checked against (decision 314(b)): each case is a document or layer plus
its expected resolved geometry/attributes, produced by the REAL server code. Regenerate with:
    python scripts/export_studio_fixtures.py
The guard test backend/tests/parity_0120/card_engine/test_fixtures.py fails if a fixture drifts from the code.
Needs Django settings only for gettext; stubbed settings are enough (see `_bootstrap`).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend" / "apps" / "card_designs" / "fixtures"
sys.path.insert(0, str(ROOT / "backend"))


def _bootstrap():
    import django
    from django.conf import settings
    if not settings.configured:
        settings.configure(USE_I18N=False, INSTALLED_APPS=[])
        django.setup()


def _uuid(n):
    return f"00000000-0000-4000-8000-{n:012d}"


def _text(n, **extra):
    base = {"id": _uuid(n), "kind": "text", "name": "t", "x_mm": 3, "y_mm": 10, "w_mm": 48, "h_mm": 20,
            "text": "", "font_family": "Outfit", "font_weight": 400, "font_size_pt": 16, "colour": "#142C2A"}
    return {**base, **extra}


def plan_cases():
    from apps.card_designs import rendering_rich, studio_geometry
    from apps.card_designs.layout_layers import normalize_layer
    from apps.card_designs.rendering import RenderContext
    cases = []
    for index, (iw, ih, bw, bh, fit, zoom, fx, fy) in enumerate((
            (600, 800, 40, 42, "cover", 1, 50, 50), (600, 800, 40, 42, "contain", 1, 50, 50),
            (600, 800, 40, 42, "stretch", 1, 50, 50), (600, 800, 40, 42, "cover", 2, 25, 75),
            (1600, 900, 85.6, 53.98, "cover", 1.5, 80, 20), (1600, 900, 85.6, 53.98, "contain", 1, 0, 100))):
        left, top, width, height = studio_geometry.place(iw, ih, bw, bh, fit, zoom, fx, fy)
        cases.append({"id": f"place/{index}", "kind": "place", "input": {
            "image": [iw, ih], "box": [bw, bh], "fit": fit, "zoom": zoom, "focal": [fx, fy]},
            "expected": {"left": round(left, 3), "top": round(top, 3), "width": round(width, 3), "height": round(height, 3)}})
    for index, spec in enumerate(({"type": "linear", "angle_deg": 180}, {"type": "linear", "angle_deg": 45},
                                  {"type": "radial", "cx_pct": 30, "cy_pct": 40, "radius_pct": 80})):
        if spec["type"] == "linear":
            expected = dict(zip(("x0", "y0", "x1", "y1"), (round(v, 3) for v in studio_geometry.gradient_line(spec, 54, 85.6))))
        else:
            expected = dict(zip(("cx", "cy", "r"), (round(v, 3) for v in studio_geometry.radial_circle(spec, 54, 85.6))))
        cases.append({"id": f"gradient/{index}", "kind": "gradient", "input": {"spec": spec, "box": [54, 85.6]}, "expected": expected})
    rich = [
        ("rich/two-weight-name", _text(1, spans=[
            {"text": "{{first_name}}\n", "font_family": "Gilroy Light", "font_weight": 300},
            {"text": "{{last_name}}", "font_family": "Gilroy ExtraBold", "font_weight": 800, "colour": "#DFFF8F"}],
            uppercase=True, align="left", font_size_pt=18, line_height=1.0), {"name": "Fathima Shenza"}),
        ("rich/highlight-centred", _text(2, text="{{role}}", font_weight=700, font_size_pt=8, align="center", valign="middle",
                                         h_mm=5, uppercase=True, tracking_pt=1,
                                         highlight={"colour": "#DFFF8F", "pad_x_mm": 1.4, "pad_y_mm": 0.5, "radius_mm": 0.8}),
         {"role": "Mentor"}),
        ("rich/wrap-shrink", _text(3, spans=[{"text": "Community "}, {"text": "hardware hackathon night", "font_weight": 700,
                                                                       "size_scale": 1.3}], h_mm=18, w_mm=40), {}),
        ("rich/underline-script", _text(4, text="{{team}}", font_family="Pacifico", font_size_pt=11, h_mm=6,
                                        underline={"colour": "#006E63", "thickness_pt": 1.5, "offset_pt": 2}), {"team": "Electronics"}),
    ]
    for name, layer, values in rich:
        normalised = normalize_layer(layer, 54, 85.6, "cr80-portrait")
        spans = rendering_rich.resolve(normalised, RenderContext(values=values))
        from reportlab.lib.units import mm
        result = rendering_rich.plan(spans, normalised, normalised["w_mm"] * mm, normalised["h_mm"] * mm)
        cases.append({"id": name, "kind": "rich_plan", "input": {"layer": normalised, "values": values}, "expected": {
            "scale": result["scale"], "lines": [{
                "text": "".join(part["text"] for part in line["parts"]), "baseline": round(line["baseline"], 2),
                "x": round(line["x"], 2), "width": round(line["width"], 2), "size": round(line["size"], 2)}
                for line in result["lines"]],
            "bars": [{key: round(value, 2) for key, value in bar.items()} for bar in result["bars"]],
            "rules": [{key: round(value, 2) for key, value in rule.items()} for rule in result["rules"]]}})
    cases += studio2_cases()
    return {"description": "Resolved Card Studio geometry (decision 314b). Lengths in mm unless a plan value (points).",
            "cases": cases}


def studio2_cases():
    """CARD-STUDIO-2 (decision 344): polygon shapes, icons, the photo variant pick and the mask radius (TS twins:
    studioMath.polygonPoints, IconLayerView, photoVariant.pickPhoto, studioMath.roundedRadius)."""
    from types import SimpleNamespace
    from apps.card_designs import studio_geometry, studio_icons
    from apps.card_designs.rendering_photo import photo_source
    cases = []
    for shape in studio_geometry.POLYGON_SHAPES:
        for width, height in ((20, 20), (30, 12)):
            cases.append({"id": f"polygon/{shape}/{width}x{height}", "kind": "polygon",
                          "input": {"shape": shape, "box": [width, height]},
                          "expected": {"points": [list(point) for point in studio_geometry.polygon_points(shape, width, height)]}})
    for key in ("star", "id_card", "gear"):
        scale, dx, dy = studio_icons.fit(30, 12)
        cases.append({"id": f"icon/{key}", "kind": "icon", "input": {"icon": key, "box": [30, 12]},
                      "expected": {"scale": round(scale, 4), "dx": round(dx, 4), "dy": round(dy, 4),
                                   "paths": studio_icons.catalogue()[key]["paths"]}})
    for variant in ("original", "cutout", "auto"):
        for has_cutout in (True, False):
            for use_cutout in (True, False):
                context = SimpleNamespace(photo=b"original", photo_cutout=b"cutout" if has_cutout else None,
                                          use_cutout=use_cutout)
                _data, is_cutout = photo_source({"variant": variant}, context)
                cases.append({"id": f"photo/{variant}/{'cut' if has_cutout else 'none'}/{'chosen' if use_cutout else 'not'}",
                              "kind": "photo_pick", "input": {"variant": variant, "cutout": has_cutout, "use_cutout": use_cutout},
                              "expected": {"pick": "cutout" if is_cutout else "original"}})
    from apps.card_designs import barcode_symbols
    text_mm = 6 * 1.25 * 25.4 / 72
    for symbology, payload, box in (("code128", "TNK-0042", (40, 10)), ("code39", "TNK-0042", (45, 10)),
                                    ("ean13", "590123412345", (32, 12)), ("upca", "03600029145", (32, 12)),
                                    ("pdf417", "TNK-0042", (40, 12)), ("datamatrix", "TNK-0042", (14, 14)),
                                    ("aztec", "TNK-0042", (14, 14))):
        encoded = barcode_symbols.encode(symbology, payload)
        text_h = text_mm if encoded["kind"] == "linear" else 0
        cases.append({"id": f"barcode/{symbology}", "kind": "barcode",
                      "input": {"symbology": symbology, "payload": payload, "box": list(box), "text_mm": round(text_h, 4)},
                      "expected": {"encoding": encoded, "rects": barcode_symbols.rects(encoded, box[0], box[1], text_h),
                                   "minimum": {source: barcode_symbols.MINIMUM_MM[symbology][0][index]
                                               for index, source in enumerate(("number", "desk"))},
                                   "min_height": barcode_symbols.MINIMUM_MM[symbology][1]}})
    for width, height, radius in ((20, 30, None), (20, 30, 4), (20, 30, 0), (20, 6, 9)):
        cases.append({"id": f"mask-radius/{width}x{height}/{radius}", "kind": "mask_radius",
                      "input": {"box": [width, height], "radius_mm": radius},
                      "expected": {"radius": round(studio_geometry.mask_radius("rounded", width, height, radius), 4)}})
    return cases


def compat_cases():
    """Old v2 documents: normalising them under v3 changes only `version` (layers and sides are byte-equal)."""
    from apps.card_designs.default_templates import build
    from apps.card_designs.layout import normalize_document
    cases = []
    for key in ("classic", "bold", "minimal", "community", "student", "kasavu", "ribbon", "confetti"):
        document = build(key, "member_cards", "light")
        document["version"] = 2
        clean = normalize_document(document, check_contrast=False)
        cases.append({"id": f"compat/{key}", "input": document, "expected": clean})
    return {"description": "A v2 document normalises to the same sides under v3; only `version` becomes 3.", "cases": cases}


CERT_VALUES = {
    "name": "Fathima Shenza", "recipient": "Fathima Shenza", "event": "Community Hardware Hackathon 2026",
    "event_date": "14 November 2026", "issue_date": "2 December 2026", "organisation": "Tinkerspace", "kind": "Winner",
    "award": "1st place - Best hardware hack", "role": "Participant", "place": "1st place", "serial": "SW-2026-000042",
    "serial_short": "SW-2026-", "hours": "6", "achievement": "1st place - Best hardware hack",
}


def _v2_text(n, text, x, y, w, h, **extra):
    base = {"id": _uuid(n), "order": n, "type": "text", "x_mm": x, "y_mm": y, "width_mm": w, "height_mm": h, "rotation": 0,
            "text": text, "font_family": "Outfit", "font_weight": 400, "font_size_pt": 14, "align": "center",
            "shrink_to_fit": True, "uppercase": False, "tracking_pt": 0, "line_height": 1.3, "colour_token": "ink"}
    return {**base, **extra}


def _certificate_layouts():
    """Stored v2 certificate layouts: wrapped and shrunk text, uppercase, tracking, signatures, QR, certificate number."""
    from apps.events.certificates.layout import normalize_document, upgrade_legacy
    layers = [
        _v2_text(0, "Certificate of {{kind}}", 20, 30, 257, 18, font_size_pt=30, font_weight=700, uppercase=True, tracking_pt=2),
        _v2_text(1, "{{name}}", 20, 76, 257, 20, font_size_pt=34, font_weight=700, colour_token="teal"),
        _v2_text(2, "{{event}}", 60, 110, 177, 22, font_size_pt=20, font_weight=700),
        _v2_text(3, "{{eventDate}} - issued {{issueDate}} by {{organisation}}", 20, 138, 257, 9, font_size_pt=12, align="left"),
        _v2_text(4, "Role: {{crewRole}} / {{role}} / {{award}} {{place}}", 20, 150, 120, 8, font_size_pt=11, align="right",
                 colour="#006E63"),
        {"id": _uuid(5), "order": 5, "type": "signature", "x_mm": 30, "y_mm": 160, "width_mm": 70, "height_mm": 30,
         "rotation": 0, "signature_slot": 1, "font_family": "Outfit", "font_weight": 600, "font_size_pt": 11, "align": "center",
         "colour_token": "ink", "uppercase": False, "tracking_pt": 0, "shrink_to_fit": True, "line_height": 1.3},
        {"id": _uuid(6), "order": 6, "type": "certificate_qr", "x_mm": 8, "y_mm": 177, "width_mm": 25, "height_mm": 25,
         "rotation": 0, "resource_slot": "certificate_verification_qr"},
        {"id": _uuid(7), "order": 7, "type": "certificate_id", "x_mm": 40, "y_mm": 198, "width_mm": 249, "height_mm": 8,
         "rotation": 0, "font_family": "Outfit", "font_weight": 400, "font_size_pt": 7, "align": "right", "shrink_to_fit": True,
         "text": "", "uppercase": False, "tracking_pt": 0, "line_height": 1.3, "colour_token": "ink"},
    ]
    return {"wide": {"version": 2, "page_width_mm": 297.0, "page_height_mm": 210.0, "layers": layers},
            "legacy-labels": upgrade_legacy({"page_width_mm": 297.0, "page_height_mm": 210.0, "name_box": {
                "x_mm": 25.0, "y_mm": 76.0, "width_mm": 247.0, "height_mm": 18.0, "font_size_pt": 24.0, "bold": True,
                "align": "center"}})}, normalize_document


def _text_plan(document, values):
    from reportlab.lib.units import mm
    from apps.card_designs import rendering_text
    from apps.card_designs.data_fields import merge
    plan = []
    for layer in document["front"]["layers"]:
        if layer["kind"] not in ("text", "certificate_id"):
            continue
        text = merge(layer["text"], values)
        if not text.strip():
            continue
        size, lines = rendering_text.fit_compat(text, layer, layer["w_mm"] * mm, layer["h_mm"] * mm)
        plan.append({"id": layer["id"], "size_pt": round(size, 2), "lines": lines,
                     "first_baseline_from_top_mm": round(size * 25.4 / 72, 2),
                     "leading_pt": round(size * layer["line_height"], 2)})
    return plan


def certificate_compat_cases():
    """Old v2 certificate layouts: the compiled v3 document (`compile_v2`) and the v2-metrics text plan (golden)."""
    from apps.card_designs.certificate_compile import compile_v2
    layouts, normalize = _certificate_layouts()
    cases = []
    for name, layout in layouts.items():
        layout = normalize(layout)
        document = compile_v2(layout, {"merge": {"role": "Participant"}})
        cases.append({"id": f"certificate-compat/{name}", "layout": layout, "values": CERT_VALUES,
                      "expected": {"document": document, "text_plan": _text_plan(document, CERT_VALUES)}})
    return {"description": "A stored v2 certificate layout -> v3 document + text plan under the v2 metrics (frozen merge present).",
            "cases": cases}


def certificate_plan_cases():
    """Certificate-only geometry for the TS twin: signature-row cells, seal radii, built-in templates (normalised)."""
    from apps.card_designs import rendering_certificate
    from apps.card_designs.default_templates import CERTIFICATE_LOOKS, THEMES, build_certificate
    from apps.card_designs.layout import normalize_document
    cases = []
    for index, (width, gap, count) in enumerate(((200, 14, 3), (200, 14, 2), (130, 8, 1), (180, 4, 3))):
        cells = [{"offset": round(offset, 3), "width": round(cell, 3)} for offset, cell in rendering_certificate.cells(width, gap, count)]
        cases.append({"id": f"signature-row/{index}", "kind": "signature_row", "input": {"width_mm": width, "gap_mm": gap, "count": count},
                      "expected": {"cells": cells}})
    cases.append({"id": "signature/fractions", "kind": "signature_fractions", "input": {},
                  "expected": {"image": rendering_certificate.IMAGE, "rule": rendering_certificate.RULE,
                               "name": rendering_certificate.NAME, "rule_inset": rendering_certificate.RULE_INSET}})
    cases.append({"id": "seal/geometry", "kind": "seal", "input": {"box_mm": [28, 28]},
                  "expected": {"scallops": rendering_certificate.SCALLOPS, "star_points": rendering_certificate.STAR_POINTS,
                               "inner_ring_radius": rendering_certificate.INNER_RING,
                               "ring_text_radius": rendering_certificate.RING_TEXT_RADIUS,
                               "ring_text_size_of_ring_radius": rendering_certificate.RING_TEXT_SIZE,
                               "ring_text_max_degrees": rendering_certificate.RING_SPAN_DEG,
                               "ring_circle_radius": rendering_certificate.OUTER_RING, "min_ring_text_pt": 5}})
    for theme in THEMES:
        for key in CERTIFICATE_LOOKS:
            cases.append({"id": f"template/{key}/{theme}", "kind": "template",
                          "input": {"key": key, "theme": theme},
                          "expected": {"document": normalize_document(build_certificate(key, theme))}})
    return {"description": "Certificate-only geometry and the built-in certificate templates (normalised, AA-checked).", "cases": cases}


def main():
    _bootstrap()
    OUT.mkdir(exist_ok=True)
    for name, data in (("studio_plan_cases.json", plan_cases()), ("studio_compat_cases.json", compat_cases()),
                       ("certificate_compat_cases.json", certificate_compat_cases()),
                       ("certificate_plan_cases.json", certificate_plan_cases())):
        (OUT / name).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print("wrote", name)


if __name__ == "__main__":
    main()
