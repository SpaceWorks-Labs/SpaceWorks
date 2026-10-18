# Space Works print faces

These static TrueType files come from the approved font kit already shipped at
`frontend/public/fonts/`: Gilroy Regular/Medium/SemiBold/Bold, and Unbounded's
400/500/600/700 instances. FontTools decoded WOFF2 and instantiated Unbounded's
weight axis without synthesizing styles or changing glyph outlines. No italic
face exists in that kit, so the layout validator refuses italic.

Gilroy follows the repository's existing brand-kit licence. Unbounded follows
the SIL Open Font License in `OFL-Unbounded.txt`. Script coverage beyond the kit
continues through the existing printable engine's bundled Noto fallback.
