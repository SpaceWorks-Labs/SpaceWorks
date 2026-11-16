# Upload formats, limits and retention

**These are code limits, not an acceptance claim.** The upload features are
per-space switches, off for a new space. The real-tool export test (open-source tools: Inkscape,
PrusaSlicer, arduino-cli, FreeCAD, KiCad) runs in the release test phase; proprietary formats
with no owner samples (SolidWorks, Inventor, F3D, Altium, Eagle, LightBurn, CDR, SKP, DWG, and
embroidery PES/DST unless Ink/Stitch installs) are waived for this release.

`maker_formats/registry.py` defines the opt-in `hackathon-maker-v1` policy. The existing
machine/service policy remains in `maker_formats/legacy.py`; enabling a hackathon policy
does not widen ordinary machine uploads. The config model's current `upload_policy="maker"`
default must be reconciled by the integration provider with this versioned registry before
enablement; an unavailable/unsupported policy refuses.

Files are classified by extension **and subtype/content**, not MIME or suffix alone.
Compound suffixes include `.gcode.3mf` and `.tar.gz`. Declared MIME aliases are closed;
an allowed `application/octet-stream` declaration still undergoes content validation.
Filenames cannot contain paths, controls or normalization tricks. Opaque/proprietary
structural checks are not proof that every vendor version works: licensed real-export
acceptance, including SolidWorks/Inventor variants, remains open.

| Family | Declared formats / behaviour |
| --- | --- |
| 2D fabrication | SVG, ASCII/binary DXF, PDF/PostScript AI, EPS, LightBurn, Studio3, CDR |
| 3D printing | STL, OBJ/MTL, 3MF and slicer subtypes, AMF, PLY, G-code/GCO/G, BGCODE |
| CNC | NC/TAP/NGC/CNC toolpath text, CRV/CRV3D |
| CAD | STEP/STP/STPZ, IGES/IGS, F3D, SLDPRT/SLDASM/SLDDRW, IPT/IAM, SKP, FCStd, SCAD, Blend, DWG, 3DM |
| PCB | Gerber including `.g1`–`.g30`, Excellon DRL/XLN, Gerber ZIP, ODB TGZ, IPC-2581 XML/CVG, KiCad current/legacy, Eagle, Altium PCB/schematic/project, EasyEDA JSON/EPRO, Fritzing FZZ, LTspice ASC, BOM/pick-place CSV and position files |
| Firmware | INO/Python/C/C++ headers/source, Intel HEX, BIN, UF2, ELF (ARM/AVR/Xtensa/RISC-V) |
| Embroidery | PES, DST, JEF, EXP, VP3 |
| Archives/source | ZIP, TAR.GZ/TGZ, 7Z; bounded listing, never server execution |
| Media | MP4/MOV, WebM/MKV originals; PPTX/ODP decks; JPEG/PNG/WebP images |

The registry is authoritative for exact accepted subtypes and per-file caps. Representative
caps: images 5 MiB each, video 500 MiB, deck 50 MiB, STL/OBJ/3MF and most CAD 200 MiB,
Gerber 20 MiB, Gerber ZIP 50 MiB, firmware text 1 MiB, UF2/ELF 32 MiB. Event overrides
can lower accepted file/group bounds. An extension's structural acceptance is distinct
from a working preview and from the mandatory real-export sample matrix.

## Budgets and media validation

All MiB values below mean 1,048,576 bytes. Managed event allowance is **decimal 25 GB =
25,000,000,000 bytes**, separate from the ordinary tenant base storage entitlement.
`EventAssetUsage` counts stored bytes plus active reservations for the entire event.
Self-host event budget can be `null` (unlimited event pool) or an explicit byte limit;
per-file, per-group, asset-count and per-submission limits still apply. Managed storage
pool/provider accounting and imported usage rebuilding remain pending integration.

| Submission group | Aggregate cap (MiB) |
| --- | ---: |
| video | 500 |
| deck | 50 |
| images | 50, at most 10 images |
| source | 200 |
| hardware-pcb | 150 |
| hardware-cad | 500 |
| firmware | 50 |
| fab-2d | 150 |
| fab-3dprint | 500 |
| fab-cnc | 300 |
| embroidery | 50 |
| archives | 200 |

The shared reservation helper caps a submission/owner collection at **1536 MiB and
100 assets**. Reservations count until confirmed cleanup; canonical image growth needs
additional reservation before promotion. Lowering a budget below used+reserved refuses.
The account Saved details résumé pool is separate: PDF-only, **10 MiB/file**, **50 MiB
per account** by default; self-host can raise that pool. B's event résumé copy has independent
event ownership/quota/validation; its PDF file cap is also 10 MiB. Deleting the vault source
does not erase submitted evidence.

Current `VideoPolicy`: 30–240 seconds; height 720–2160 pixels; width 1–3840 pixels.
Configuration validation requires a maximum-width setting of at least 1280; it does not
impose a 1280-pixel minimum on the input. Exactly one video stream in a supported container
is required. The probe reports codec/browser playability; unsupported browser playback
can use authenticated original download. No transcoding occurs. The runtime currently
passes the default policy; organizer-specific lower policy wiring is not established here.

STL/OBJ/3MF mesh and Gerber/drill previews have lazy bounded workers; STEP/IGES loads on
explicit request. External textures/references are refused. ZIP listing, expansion, mesh,
time/output limits and cancellation guard the browser. KiCad files (boards, schematics,
symbols, footprints, projects and KiCad 5) are download-only by design:
there is no in-browser KiCad viewer; the file offers only its original download. Vendor
bundling/WASM APIs and actual browser previews of the other formats still need acceptance.

### Preview acceptance

KiCad preview acceptance is **not applicable** in this release: no KiCad viewer is provided, so there is nothing
to accept alongside the existing previews. The existing 3D and Gerber previews
keep the acceptance status recorded above.
Images are metadata-stripped/re-encoded; text/CSV/toolpath previews escape content and
protect exported cells from spreadsheet formulas. Accepted files are never executed.

## Retention and removal

The retention service accepts `results`, `cancelled` and `fallback` anchors and uses
**365 days**. First results publication is recorded once; subsequent corrections/uploads
cannot extend an existing deadline. Cancellation/fallback policy must be installed by the
lifecycle provider; this checkout has helpers, not proof that every anchor is invoked.
Absolute expiry and hashes survive import; import must not calculate a new year.

At logical expiry, gated reads stop (410 for an otherwise authorized known asset), even
if storage cleanup is unavailable. Cleanup removes final, staging and verification
versions/multipart work; failed deletion continues to consume its reservation/charge.
Records, immutable snapshots and hashes remain. Public cards show expired files without
download/player controls. Feature/module disablement hides live surfaces but retains data;
it is not expiry, deletion, purge or revocation of independent backup archives.

Authored abandoned-upload cleanup selects idle reserved/uploading rows after 24 hours;
unattached submission files can be selected 30 days after event end. Persisted work and
absence rechecks are separate from the retained business records. Durable purge receipts
and always-available cleanup scheduling remain required; key collection alone is insufficient.

Live object expiry does **not** erase previously created backup archives. Backup retention
and offsite custody follow their own policies. New captures require ready unexpired bytes
with matching canonical size/hash, treat terminal expired bytes as expected absence, and
refuse capture during cleanup/promotion or overdue-ready retention finalization. Missing
ready bytes are corruption, not an acceptable expired record. See [operator notes](operations.md).
