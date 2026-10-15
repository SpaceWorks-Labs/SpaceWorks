> **Superseded 2026-10-16** by `welcome-and-dark-spec.md` §6 and `dark-tokens-v3.json`: the owner approved the Deep Ink + Maker Teal ("teal-lit ink") dark surfaces, a Citron focus ring and solid status marks. Accent stays saturated Maker Teal. This page is kept as history.

# Owner dark-mode contrast pass

The owner retained the Deep Ink base and asked for stronger separation and saturated teal actions. Light tokens remain unchanged. All mixes use the original `brand_tokens_v2.py` sRGB-channel rounding and WCAG functions; the adapted copy and full console report are in `scratchpad/brand_tokens_owner_pass.py` and `scratchpad/dark-contrast-owner-pass.txt`. The companion JSON records every resulting token and its source.

| Token | Value | Derivation | Contrast |
|---|---|---|---|
| `bg` | `#142C2A` / 20 44 42 | brand (reversed ground) | Warm Cream text: 13.60:1 |
| `sidebar` | `#1B3230` / 27 50 48 | brand-mix: Deep Ink + 3% Warm Cream | Warm Cream text: 12.52:1 |
| `surface` | `#223835` / 34 56 53 | brand-mix: Deep Ink + 6% Warm Cream | Warm Cream text: 11.49:1 |
| `panel` | `#304441` / 48 68 65 | brand-mix: Deep Ink + 12% Warm Cream | Warm Cream text: 9.54:1 |
| `hover` | `#3C4E4A` / 60 78 74 | brand-mix: Deep Ink + 17% Warm Cream | Warm Cream text: 8.13:1 |
| `line` | `#56645F` / 86 100 95 | brand-mix: Deep Ink + 28% Warm Cream | Warm Cream text: 5.72:1 |
| `outline` | `#959A93` / 149 154 147 | brand-mix: Deep Ink + 55% Warm Cream | bg: 5.14:1 / surface: 4.34:1 / panel: 3.61:1 / hover: 3.08:1 |
| `muted` | `#BDBCB3` / 189 188 179 | brand-mix: Cream + 28% Ink | worst universal background: 4.60:1 |
| `accent` | `#006E63` / 0 110 99 | brand Maker Teal; boundary supplied by accent-ink | Warm Cream label: 5.68:1 |
| `accent-hover` | `#02675D` / 2 103 93 | brand-mix: accent + 10% Ink | Warm Cream label: 6.24:1 |
| `accent-active` | `#046158` / 4 97 88 | brand-mix: accent + 20% Ink | Warm Cream label: 6.78:1 |
| `on-accent` | `#FFF4E8` / 255 244 232 | brand Warm Cream | Warm Cream text: 1.00:1 |
| `accent-soft` | `#2D4743` / 45 71 67 | brand-mix: panel + 6% accent | Warm Cream text: 9.24:1 |
| `emphasis-soft` | `#3C4741` / 60 71 65 | brand-mix: panel + 6% emphasis | Warm Cream text: 8.92:1 |
| `success-soft` | `#3B4F46` / 59 79 70 | brand-mix: panel + 6% success | Warm Cream text: 8.09:1 |
| `warn-soft` | `#3C4D41` / 60 77 65 | brand-mix: panel + 6% warn | Warm Cream text: 8.31:1 |
| `info-soft` | `#384C4C` / 56 76 76 | brand-mix: panel + 6% info | Warm Cream text: 8.39:1 |
| `accent-ink` | `#A3C4B8` / 163 196 184 | brand-mix: dark accent + 64% Cream | worst universal background: 4.66:1 |

Primary actions use pure Maker Teal with Warm Cream labels (5.68:1, rising to 6.24/6.78 on hover/active). Saturated teal cannot itself supply a 3:1 boundary against the Deep Ink ground while keeping a Cream label at 4.5:1. The existing accent-ink boundary supplies 5.49:1 against the raised panel; the sidebar selected state uses that same visible outline. Active tabs use accent-ink for their underline. Input grounds use surface; table headers use hover.

Every universal text pair remains at least 4.60:1. Existing Yuyu danger and brand status colours remain unchanged; the darkest status text pair is danger on success-soft at 4.62:1. Fixed soft fills use 6% of their tone over the raised panel. Tenant overrides still request up to 12% and reduce the tint until every fixed ink is readable. No accepted tenant colour is rejected.
