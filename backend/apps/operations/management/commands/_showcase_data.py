"""Fictional fixture data for `seed_showcase`. Every person here is invented."""

SLUG = "tinkerspace"
NAME = "Tinkerspace"
ORGANIZATION = "Tinkerspace Collective"
LOCATION = "Unit 4, Canal Street Works"
SUPERADMIN = ("tinker_root", "Tinkerspace Platform Admin")

# (username, display name, built-in role slug)
STAFF = (
    ("tinker_manager", "Maya Fernandes", "space_manager"),
    ("tinker_inventory", "Omar Siddiqui", "inventory_manager"),
    ("tinker_machines", "Hana Kowalski", "machine_manager"),
    ("tinker_desk", "Ben Okafor", "handover"),
    ("tinker_shop", "Priya Shah", "shop_manager"),
)

MEMBERS = (
    ("asha_menon", "Asha Menon"),
    ("ravi_kumar", "Ravi Kumar"),
    ("lena_ortiz", "Lena Ortiz"),
    ("tomas_berg", "Tomas Berg"),
    ("meilin_chua", "Mei Lin Chua"),
    ("kofi_mensah", "Kofi Mensah"),
    ("priya_nair", "Priya Nair"),
    ("jonas_weber", "Jonas Weber"),
    ("sara_haddad", "Sara Haddad"),
    ("diego_ramos", "Diego Ramos"),
    ("aiko_tanaka", "Aiko Tanaka"),
    ("noor_rahman", "Noor Rahman"),
)
RESTRICTED_MEMBER = ("felix_grant", "Felix Grant")

CATEGORIES = (
    ("Electronics", "cpu"),
    ("Hand Tools", "wrench"),
    ("Power Tools", "drill"),
    ("Measuring", "ruler"),
    ("Textiles", "scissors"),
    ("3D Printing Supplies", "printer"),
    ("Consumables", "package"),
)

# (label, location)
BOXES = (
    ("Electronics Drawer A", "Electronics bay, rack 1"),
    ("Electronics Drawer B", "Electronics bay, rack 1"),
    ("Tool Wall Tote", "Tool wall"),
    ("Power Tool Case 1", "Power tool cabinet"),
    ("Power Tool Case 2", "Power tool cabinet"),
    ("Measuring Kit Box", "Measurement drawer"),
    ("Textile Studio Crate", "Textile studio"),
    ("Print Supplies Bin", "Print farm shelf"),
)

EXACT, STATUS, HIDDEN = "exact_count", "status_only", "hidden"

# (name, category, box index, quantity, availability mode, is_public, reorder point,
#  reorder quantity). Quantity-tracked: stock arrives through the availability
#  module's audited intake. A quantity of 0 is never used here.
COUNTED_PRODUCTS = (
    ("Arduino Uno R4", "Electronics", 0, 20, EXACT, True, 4, 10),
    ("ESP32 Dev Board", "Electronics", 0, 24, EXACT, True, 5, 12),
    ("Raspberry Pi 5 Kit", "Electronics", 1, 3, EXACT, True, 4, 6),
    ("Soldering Station", "Electronics", 1, 6, STATUS, True, 0, 0),
    ("Breadboard Starter Kit", "Electronics", 1, 30, EXACT, True, 0, 0),
    ("Screwdriver Set", "Hand Tools", 2, 10, EXACT, True, 0, 0),
    ("Precision Tweezers", "Hand Tools", 2, 12, STATUS, True, 0, 0),
    ("Wire Strippers", "Hand Tools", 2, 8, EXACT, True, 0, 0),
    ("Hex Key Set", "Hand Tools", 2, 10, STATUS, True, 0, 0),
    ("Japanese Pull Saw", "Hand Tools", 2, 4, HIDDEN, True, 0, 0),
    ("Orbital Sander", "Power Tools", 3, 3, STATUS, True, 0, 0),
    ("Rotary Tool Kit", "Power Tools", 3, 3, EXACT, True, 0, 0),
    ("Heat Gun", "Power Tools", 4, 4, STATUS, True, 0, 0),
    ("Digital Caliper", "Measuring", 5, 10, EXACT, True, 0, 0),
    ("Multimeter", "Measuring", 5, 12, EXACT, True, 3, 6),
    ("Steel Rule 60 cm", "Measuring", 5, 15, STATUS, True, 0, 0),
    ("Fabric Shears", "Textiles", 6, 6, EXACT, True, 0, 0),
    ("Embroidery Hoop Set", "Textiles", 6, 5, HIDDEN, True, 0, 0),
    ("PLA Filament 1 kg", "3D Printing Supplies", 7, 14, EXACT, True, 5, 10),
    ("PETG Filament 1 kg", "3D Printing Supplies", 7, 3, EXACT, True, 4, 10),
    ("Nozzle Assortment", "3D Printing Supplies", 7, 6, STATUS, False, 0, 0),
    ("Spare Build Plate", "3D Printing Supplies", 7, 2, HIDDEN, False, 0, 0),
    ("Solder Wire Spool", "Consumables", 1, 2, EXACT, True, 3, 6),
    ("Heat Shrink Assortment", "Consumables", 1, 9, STATUS, True, 0, 0),
    ("Sandpaper Pack", "Consumables", 2, 20, EXACT, True, 0, 0),
    ("Safety Glasses", "Consumables", 2, 15, EXACT, True, 0, 0),
)

# (name, category, box index, unit count, availability mode, is_public).
# QR-tracked: one asset row and one active QR label per unit.
TRACKED_PRODUCTS = (
    ("Four-channel Oscilloscope", "Electronics", 0, 3, STATUS, True),
    ("Bench Power Supply", "Electronics", 1, 3, EXACT, True),
    ("Cordless Drill Kit", "Power Tools", 3, 4, EXACT, True),
    ("Jigsaw", "Power Tools", 4, 2, STATUS, True),
    ("Laser Distance Meter", "Measuring", 5, 2, EXACT, True),
    ("Thermal Camera", "Measuring", 5, 1, HIDDEN, False),
    ("Sewing Machine", "Textiles", 6, 3, EXACT, True),
)

# A running hackathon judged by pairwise comparison. (leader, teammate, title, description).
HACKATHON = {
    "title": "Canal Street Build Weekend",
    "description": "A 24-hour hardware hackathon: build something useful for the neighbourhood.",
    "guidance": "Which project would you rather see installed on Canal Street next month?",
    "projects": (
        ("asha_menon", "meilin_chua", "Rainwater Gauge", "Solar logger that texts the allotment group when the butt is full."),
        ("ravi_kumar", "kofi_mensah", "Bike Shed Lock", "NFC lock for the shared bike shed, with a paper fallback key."),
        ("lena_ortiz", "aiko_tanaka", "Quiet Hours Light", "A traffic-light sign that shows when the workshop is in quiet hours."),
        ("tomas_berg", "noor_rahman", "Tool Library Kiosk", "A tablet kiosk that shows which tools are in and lends them out."),
    ),
    "judges": ("priya_nair", "jonas_weber", "sara_haddad"),
}
