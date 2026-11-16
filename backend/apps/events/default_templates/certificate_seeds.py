"""Three certificate families, six themed immutable catalogue candidates."""

from uuid import NAMESPACE_URL, uuid5

from .manifest import CERTIFICATE_FAMILIES, THEMES, SEED_VERSION, artwork_resource


def certificate_seed(family, theme):
    """Build fresh data for E's validator/copy workflow; never installs a revision."""
    if family not in CERTIFICATE_FAMILIES or theme not in THEMES:
        raise ValueError("Unknown certificate family or theme")
    seed_id = f"certificate-{family}"
    resource = artwork_resource(seed_id, theme)
    layers = []

    def add(kind, box, **fields):
        order = len(layers)
        layers.append({
            "id": str(uuid5(NAMESPACE_URL, f"spaceworks:{seed_id}:{theme}:{order}")),
            "order": order, "type": kind,
            **dict(zip(("x_mm", "y_mm", "width_mm", "height_mm"), box)),
            "rotation": 0, **fields,
        })

    def text(value, box, size, *, family="Gilroy", weight=500, align="left"):
        add("text", box, text=value, font_family=family, font_weight=weight,
            font_size_pt=size, align=align, shrink_to_fit=True,
            colour_token="ink", line_height=1.2)

    add("image", (0, 0, 297, 210), resource_id=resource["id"])
    # The logo slot includes a square for the supplied symbol, ≥12 mm in print.
    # E fits the complete selected master with H/4 clear space, never stretches it.
    add("logo", (25, 22, 16, 16), resource_slot="logo")
    text("Certificate", (25, 55, 247, 18), 27, family="Unbounded", weight=600)
    text("{{name}}", (25, 83, 247, 25), 32, weight=600)
    text("{{event}}", (25, 116, 222, 18), 18, weight=600)
    text("{{eventDate}}", (25, 140, 194, 8), 11)
    text("{{organisation}}", (25, 166, 194, 9), 11)
    text("Issued {{issueDate}}", (25, 180, 194, 8), 9)
    add("certificate_qr", (247, 155, 25, 25),
        resource_slot="certificate_verification_qr")
    add("certificate_id", (221, 184, 51, 7), font_family="Gilroy",
        font_weight=500, font_size_pt=7, align="right", shrink_to_fit=True,
        colour_token="ink")
    return {
        "seed_id": seed_id, "seed_version": SEED_VERSION, "theme": theme,
        "document": {"version": 2, "page_width_mm": 297,
                     "page_height_mm": 210, "layers": layers},
        "resources": [resource],
    }


CERTIFICATE_SEEDS = tuple(certificate_seed(family, theme)
                          for family in CERTIFICATE_FAMILIES for theme in THEMES)
