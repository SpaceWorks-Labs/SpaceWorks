"""Light and dark variants of a template.

Dark swaps the cream/white card for ink and recolours only what sits directly on that
background: ink text turns cream, teal text turns citron, hairlines turn the dark line
colour. Text on a band keeps its colours, because the band does not change. The result
is checked by the same 4.5:1 rule as any save.
"""
from ..contrast import colour_under, to_hex
from .builders import CITRON, CREAM, INK, LINE, WHITE

THEMES = ("light", "dark")
DARK_BG = INK
DARK_LINE = "#4D6D67"
_TEXT_ON_DARK = {INK: CREAM, "#006E63": CITRON}


def darken_side(side):
    background = side["background"]
    if background.get("kind") != "colour" or background["colour"] not in (CREAM, WHITE):
        return side
    side = {**side, "background": {"kind": "colour", "colour": DARK_BG}, "layers": [dict(layer) for layer in side["layers"]]}
    for index, layer in enumerate(side["layers"]):
        kind = layer["kind"]
        if kind in ("text", "data_field"):
            if to_hex(colour_under(side, index)) == DARK_BG:
                layer["colour"] = _TEXT_ON_DARK.get(layer["colour"], layer["colour"])
        elif kind == "perforation" and layer["colour"] == LINE:
            layer["colour"] = DARK_LINE
        elif kind == "shape" and layer.get("stroke") == LINE:
            layer["stroke"] = DARK_LINE
    return side


def apply(document, theme):
    if theme == "light":
        return document
    return {**document, "front": darken_side(document["front"]), "back": darken_side(document["back"])}
