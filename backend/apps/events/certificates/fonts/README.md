# Space Works print faces

Only redistributable faces ship here (owner decision, 2026-11-09: the repository is
AGPL, so the commercial Gilroy Regular/Medium/SemiBold/Bold files were removed).

| File | Source | Licence | Used by |
|---|---|---|---|
| `Outfit-400/500/600/700.ttf` | static instances of `frontend/public/fonts/Outfit-Variable.woff2` (fontTools `instancer`, no outline edits) | SIL OFL 1.1, `OFL-Outfit.txt` (no Reserved Font Name) | PDF/card text for the stored `"Gilroy"` design token; share-card body text |
| `Gilroy-ExtraBold.otf` | WOFF2 → OpenType container decode of the free `Gilroy-ExtraBold.woff2` (glyph outlines untouched; CFF, hence `.otf`) | Radomir Tinkov Free Font EULA, `Gilroy-Free-Font-EULA.txt` | share-card PNG title (Pillow) only |
| `Unbounded-400…700.ttf` | static instances of `Unbounded-Variable.woff2` | SIL OFL 1.1, `OFL-Unbounded.txt` | the one accent phrase |

Why the `"Gilroy"` design token renders Outfit: stored certificate/badge/card designs and
the `FontFamilyEnum` API carry `font_family: "Gilroy"` with weights 400–700, and the only
Gilroy we may ship is 300/800. ReportLab also cannot embed CFF outlines, and converting
ExtraBold to TrueType outlines would be a modification the EULA forbids (clause e). The
token is therefore kept for compatibility and resolved to Outfit at the requested weight
(`certificates/fonts.py`, `card_designs/fonts.BRAND`), so no stored design changes and no
weight is synthesised.

No italic face exists in this kit, so the layout validator refuses italic. Script
coverage beyond these faces continues through the printable engine's bundled Noto fallback.
