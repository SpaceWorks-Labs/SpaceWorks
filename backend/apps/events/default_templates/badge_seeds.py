"""Six badge designs with geometry for exactly the six frozen named stocks."""

from uuid import NAMESPACE_URL, uuid5

from .manifest import BADGE_FAMILIES, SEED_VERSION, STOCKS, THEMES, artwork_resource


def badge_seed(family, theme, stock="cr80-landscape"):
    """Stock is a render setting of one design, not a seventh template family."""
    if family not in BADGE_FAMILIES or theme not in THEMES or stock not in STOCKS:
        raise ValueError("Unknown badge family, theme or stock")
    width, height = STOCKS[stock]
    seed_id = f"badge-{family}"
    resource = artwork_resource(seed_id, theme)
    layers = []

    def add(kind, box, **fields):
        order = len(layers)
        layers.append({
            "id": str(uuid5(NAMESPACE_URL, f"spaceworks:{seed_id}:{theme}:{stock}:{order}")),
            "order": order, "type": kind,
            **dict(zip(("x_mm", "y_mm", "width_mm", "height_mm"),
                       (round(value, 3) for value in box))),
            "rotation": 0, **fields,
        })

    def text(value, box, size, *, family="Gilroy", weight=500):
        add("text", box, text=value, font_family=family, font_weight=weight,
            font_size_pt=size, align="left", shrink_to_fit=True,
            colour_token="ink", line_height=1.2)

    add("image", (0, 0, width, height), resource_id=resource["id"])
    # Slot dimensions do not select an account/profile or manufacture consent.
    add("logo", (4, 4, 13, 12), resource_slot="logo")
    text("{{event}}", (20, 4, width - 24, 10), 9, weight=600)
    text("{{eventDate}}", (20, 16, width - 24, 5), 7)
    if height > width:
        name_y = height * .29
        resource_y = height * .49
        photo_width = min(28, width * .32)
        qr_width = min(30, width * .43)
        text("{{name}}", (4, name_y, width - 8, 13), 16, weight=600)
        add("photo", (4, resource_y, photo_width, photo_width * 1.25),
            resource_slot="selected_member_photo")
        add("event_credential_qr", (width - 4 - qr_width, resource_y,
                                   qr_width, qr_width),
            resource_slot="event_credential_qr")
        text("Event pass", (4, height - 14, width - 8, 7), 8,
             family="Unbounded", weight=500)
    else:
        qr_width = 24
        add("photo", (4, 25, 18, 24), resource_slot="selected_member_photo")
        text("{{name}}", (26, 25, width - 58, 15), 12, weight=600)
        add("event_credential_qr", (width - 28, 25, qr_width, qr_width),
            resource_slot="event_credential_qr")
        text("Event pass", (26, 43, width - 58, 6), 6,
             family="Unbounded", weight=500)
    return {
        "seed_id": seed_id, "seed_version": SEED_VERSION, "theme": theme,
        "stock": stock, "no_photo_fallback": "placeholder",
        "document": {"version": 2, "page_width_mm": width,
                     "page_height_mm": height, "layers": layers},
        "resources": [resource],
    }


def iter_badge_stock_seeds():
    """Yield all 36 design×stock candidates without shared mutable documents."""
    for family in BADGE_FAMILIES:
        for theme in THEMES:
            for stock in STOCKS:
                yield badge_seed(family, theme, stock)


BADGE_SEEDS = tuple(badge_seed(family, theme)
                   for family in BADGE_FAMILIES for theme in THEMES)
