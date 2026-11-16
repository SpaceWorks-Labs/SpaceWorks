"""Versioned original artwork data. No storage, database or framework imports."""

SEED_VERSION = 1
CONTRACT_VERSION = 3
STOCKS = {'a6-portrait': (105, 148), '4x6': (101.6, 152.4), '3x4': (76.2, 101.6), '4x3': (101.6, 76.2), 'cr80-portrait': (53.98, 85.6), 'cr80-landscape': (85.6, 53.98)}
PALETTES = {'light': {'bg': '#FFF4E8', 'surface': '#F6ECE0', 'panel': '#FFFFFF', 'ink': '#142C2A', 'muted': '#5B6863', 'outline': '#828A83', 'line': '#D5D0C6', 'accent': '#006E63', 'accent-ink': '#006E63', 'accent-soft': '#E0EEEC', 'emphasis': '#FF7447', 'on-emphasis': '#142C2A', 'success': '#DFFF8F', 'on-success': '#142C2A', 'success-soft': '#FBFFF2', 'success-ink': '#536D49', 'warn': '#FFD447', 'on-warn': '#142C2A', 'warn-soft': '#FFFAE9', 'info': '#B5CDFF', 'on-info': '#142C2A', 'info-soft': '#F6F9FF', 'danger': '#B91C1C'}, 'dark': {'bg': '#142C2A', 'surface': '#193935', 'panel': '#1F433F', 'ink': '#FFF4E8', 'muted': '#C7C4BA', 'outline': '#93A198', 'line': '#4D6D67', 'accent': '#006E63', 'accent-ink': '#ABC8BC', 'accent-soft': '#1A4A45', 'emphasis': '#FF7447', 'on-emphasis': '#142C2A', 'success': '#DFFF8F', 'on-success': '#142C2A', 'success-soft': '#2C5045', 'success-ink': '#DFFF8F', 'warn': '#FFD447', 'on-warn': '#142C2A', 'warn-soft': '#2F4D40', 'info': '#B5CDFF', 'on-info': '#142C2A', 'info-soft': '#2A4D4C', 'danger': '#FCA5A5'}}
ARTWORK = (
    {'template_id': 'certificate-foundry', 'seed_version': 1, 'theme': 'light', 'path': 'artwork/certificate-foundry.light.svg', 'sha256': '1d342aaa04eccb0819548da2f399b8269a5d1fd12ffdb2a8aa1ea84ce8e6f791', 'width': 297, 'height': 210, 'stock_support': []},
    {'template_id': 'certificate-foundry', 'seed_version': 1, 'theme': 'dark', 'path': 'artwork/certificate-foundry.dark.svg', 'sha256': '9f7825cd54f549950b5bcd6b52fffefc4fec8f4b7aa3d15dec435cbb42e27935', 'width': 297, 'height': 210, 'stock_support': []},
    {'template_id': 'certificate-contour', 'seed_version': 1, 'theme': 'light', 'path': 'artwork/certificate-contour.light.svg', 'sha256': 'a690656a36c7743801ca1144e306654a299fd358b09ab7d63cf3983dd4f45e3a', 'width': 297, 'height': 210, 'stock_support': []},
    {'template_id': 'certificate-contour', 'seed_version': 1, 'theme': 'dark', 'path': 'artwork/certificate-contour.dark.svg', 'sha256': 'a0b3c7b059d1fbe60785130c9e610a4aaba7195272ed54344a4515e1790fa6d7', 'width': 297, 'height': 210, 'stock_support': []},
    {'template_id': 'certificate-blueprint', 'seed_version': 1, 'theme': 'light', 'path': 'artwork/certificate-blueprint.light.svg', 'sha256': '391060e0db226902da742dec9d3c141de2419e5fb62e868bcc82063a8fd7dc6d', 'width': 297, 'height': 210, 'stock_support': []},
    {'template_id': 'certificate-blueprint', 'seed_version': 1, 'theme': 'dark', 'path': 'artwork/certificate-blueprint.dark.svg', 'sha256': 'f9116481a3534aaf81a64afaaf7e81be46676372458c2e7034d175f16ce2384f', 'width': 297, 'height': 210, 'stock_support': []},
    {'template_id': 'badge-classic', 'seed_version': 1, 'theme': 'light', 'path': 'artwork/badge-classic.light.svg', 'sha256': 'cbb216f5fbe7d2e5775db63da07ea9d1dc443798bfdd031aaffbbfc2c8e70d2f', 'width': 100, 'height': 100, 'stock_support': ['a6-portrait', '4x6', '3x4', '4x3', 'cr80-portrait', 'cr80-landscape']},
    {'template_id': 'badge-classic', 'seed_version': 1, 'theme': 'dark', 'path': 'artwork/badge-classic.dark.svg', 'sha256': 'c319838e73fb6780a46c76c7bcf564b6fbbf64e1f453d9af7accbf78085e2fd0', 'width': 100, 'height': 100, 'stock_support': ['a6-portrait', '4x6', '3x4', '4x3', 'cr80-portrait', 'cr80-landscape']},
    {'template_id': 'badge-bold', 'seed_version': 1, 'theme': 'light', 'path': 'artwork/badge-bold.light.svg', 'sha256': '0afbb06a4f08bb1e16d35bb5384087997b088636602cfa818874862f05df6a9a', 'width': 100, 'height': 100, 'stock_support': ['a6-portrait', '4x6', '3x4', '4x3', 'cr80-portrait', 'cr80-landscape']},
    {'template_id': 'badge-bold', 'seed_version': 1, 'theme': 'dark', 'path': 'artwork/badge-bold.dark.svg', 'sha256': 'f064ddb43dd4e1375274f4fbb219d58dd05cd1451f5fcea1e77f897a890102de', 'width': 100, 'height': 100, 'stock_support': ['a6-portrait', '4x6', '3x4', '4x3', 'cr80-portrait', 'cr80-landscape']},
    {'template_id': 'badge-minimal', 'seed_version': 1, 'theme': 'light', 'path': 'artwork/badge-minimal.light.svg', 'sha256': 'cac8c414bfc8a5456df65c05b59bfaff4b2b83cd46ea80d715050f111c33b57f', 'width': 100, 'height': 100, 'stock_support': ['a6-portrait', '4x6', '3x4', '4x3', 'cr80-portrait', 'cr80-landscape']},
    {'template_id': 'badge-minimal', 'seed_version': 1, 'theme': 'dark', 'path': 'artwork/badge-minimal.dark.svg', 'sha256': 'fdf9736faf69664ebae965b7a9004d9f3b7a5d8edea90aa619f37ae5186034e3', 'width': 100, 'height': 100, 'stock_support': ['a6-portrait', '4x6', '3x4', '4x3', 'cr80-portrait', 'cr80-landscape']},
)
CERTIFICATE_FAMILIES = ("foundry", "contour", "blueprint")
BADGE_FAMILIES = ("classic", "bold", "minimal")
THEMES = ("light", "dark")


def artwork_resource(template_id, theme):
    """Return a fresh checksum-bound resource, never a URL or tenant object key."""
    from uuid import NAMESPACE_URL, uuid5
    entry = next(item for item in ARTWORK
                 if item["template_id"] == template_id and item["theme"] == theme)
    return {"id": str(uuid5(NAMESPACE_URL, "spaceworks:seed:" + entry["path"])),
            "kind": "packaged_artwork", "path": entry["path"], "sha256": entry["sha256"]}
