"""Representative curated event-site metadata, including all portable fields."""

LAYOUT = ["HERO", "ABOUT", "HIGHLIGHTS", "SCHEDULE", "SPEAKERS", "SPONSORS", "VENUE", "FAQ", "RESOURCES", "EDITORIAL"]


def venue():
    return {"name": "Community Hall", "address": "42 Workshop Road", "city": "Pune",
            "country": "India", "latitude": 18.5204, "longitude": 73.8567,
            "map_url": "https://maps.example/hall", "directions": "Enter through the east gate.",
            "parking": "Bicycle racks outside.", "public_transport": "Bus 12 stops nearby.",
            "accessibility_notes": "Step-free entrance and accessible toilets."}


def metadata():
    return {"tagline": "Build together", "accent_color": "#1a2B3c", "venue": venue(),
            "section_order": list(reversed(LAYOUT)),
            "section_enabled": {key: True for key in LAYOUT}}


def profile():
    return {"headline": "Hardware researcher", "organization": "Community Lab",
            "website_url": "https://speaker.example/about", "linkedin_url": "https://linkedin.com/in/speaker",
            "x_url": "https://x.com/speaker"}
