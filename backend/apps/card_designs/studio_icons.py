"""The Card Studio icon set (decision 344(b)): a closed, vendored library of filled vector icons.

`studio_icons.json` is the single source (the frontend ships a byte-identical copy, `studioIcons.json`, and a vitest
guard compares them). Each icon is a list of SVG path strings in a 24 x 24 box using only absolute `M L C Z`
commands; every string is filled on its own with the even-odd rule, so a compound string carries its own holes.
A document stores only the icon's KEY: no path data, no URL and no bytes ever reach a saved design.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

VIEW_BOX = 24.0
ICON_KEYS = {"icon", "colour", "flip_x"}
_TOKEN = re.compile(r"[MLCZ]|-?\d+(?:\.\d+)?")
_ARITY = {"M": 2, "L": 2, "C": 6, "Z": 0}


@lru_cache(maxsize=1)
def catalogue():
    data = json.loads((Path(__file__).with_name("studio_icons.json")).read_text(encoding="utf-8"))
    return data["icons"]


def parse(path):
    """`"M1 2 L3 4 Z"` -> [("M", (1.0, 2.0)), ("L", (3.0, 4.0)), ("Z", ())]. Raises ValueError on anything else."""
    tokens = _TOKEN.findall(path)
    if "".join(tokens).replace("-", "").replace(".", "") != re.sub(r"[\s.-]", "", path):
        raise ValueError("unsupported path syntax")
    commands, index = [], 0
    while index < len(tokens):
        op = tokens[index]
        if op not in _ARITY:
            raise ValueError(f"unexpected token {op!r}")
        count = _ARITY[op]
        args = tuple(float(value) for value in tokens[index + 1:index + 1 + count])
        if len(args) != count:
            raise ValueError("missing coordinates")
        commands.append((op, args))
        index += 1 + count
    return commands


@lru_cache(maxsize=None)
def commands(key):
    """Parsed paths of one icon; [] for an unknown key (a renderer draws nothing rather than failing a card)."""
    icon = catalogue().get(key)
    return [parse(path) for path in icon["paths"]] if icon else []


def fit(box_w, box_h):
    """Scale and offset placing the 24 x 24 icon centred inside a box (contain), same unit as the box."""
    scale = min(box_w, box_h) / VIEW_BOX
    return scale, (box_w - VIEW_BOX * scale) / 2, (box_h - VIEW_BOX * scale) / 2


def normalize(value, row, hex_colour, flag):
    """Validate an `icon` layer: a catalogue key, a #RRGGBB colour and an optional mirror."""
    key = value.get("icon")
    if not isinstance(key, str) or key not in catalogue():
        raise ValidationError({"layers": gettext("Choose an icon from the Card Studio library.")})
    row["icon"] = key
    row["colour"] = hex_colour(value.get("colour", "#142C2A"), "colour")
    if "flip_x" in value and flag(value["flip_x"], "flip_x"):
        row["flip_x"] = True
