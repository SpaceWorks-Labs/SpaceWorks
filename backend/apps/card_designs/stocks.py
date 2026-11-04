"""Physical card stocks (SPEC §3.1). Every size is millimetres, width x height.

CR80 is 85.60 x 53.98 mm everywhere (ISO/IEC 7810 ID-1); the old 54.0 is gone.
"""
from rest_framework.exceptions import ValidationError

CR80 = (85.6, 53.98)
CR79 = (83.9, 52.1)
CR100 = (98.5, 67.0)
A6 = (105.0, 148.0)

STOCKS = {
    "cr80-landscape": CR80,
    "cr80-portrait": (CR80[1], CR80[0]),
    "cr79-landscape": CR79,
    "cr79-portrait": (CR79[1], CR79[0]),
    "cr100-landscape": CR100,
    "cr100-portrait": (CR100[1], CR100[0]),
    "a6-portrait": A6,
    "a6-landscape": (A6[1], A6[0]),
    "4x3": (101.6, 76.2),
    "3x4": (76.2, 101.6),
    "4x6": (101.6, 152.4),
}
CUSTOM = "custom"
CUSTOM_MIN_MM = 40.0
CUSTOM_MAX_MM = 300.0
DEFAULT_STOCK = "cr80-landscape"
# CR stocks are small: a QR down to 18 mm still scans. Larger stocks keep 20 mm.
CR_FAMILY = ("cr80", "cr79", "cr100")
SAFE_AREA_MM = 3.0
# Sheet paper for imposition, portrait.
PAPERS = {"a4": (210.0, 297.0), "letter": (215.9, 279.4)}


def is_cr(stock):
    return stock.split("-")[0] in CR_FAMILY


def qr_minimum_mm(stock):
    return 18.0 if is_cr(stock) else 20.0


def dimensions(stock, width=None, height=None):
    """The page size a stock prints at; a custom stock carries its own size."""
    if stock in STOCKS:
        return STOCKS[stock]
    if stock != CUSTOM:
        raise ValidationError({"stock": "Choose a named stock or custom."})
    sizes = []
    for value in (width, height):
        if type(value) not in (int, float) or not CUSTOM_MIN_MM <= value <= CUSTOM_MAX_MM:
            raise ValidationError({"stock": f"A custom stock is {CUSTOM_MIN_MM:g}-{CUSTOM_MAX_MM:g} mm each side."})
        sizes.append(round(float(value), 1))
    return tuple(sizes)


def matches(stock, width, height):
    expected = dimensions(stock, width, height)
    return abs(expected[0] - width) < 0.05 and abs(expected[1] - height) < 0.05
