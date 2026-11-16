// The CardDesignDocument v3 (backend apps/card_designs/layout.py is the authority; it
// normalises every save). Millimetres, top-left origin, z-order = layer list order.
// Every v3 property is optional with a default that reproduces the v2 output, so an old document renders unchanged.

export type GradientStop = { colour: string; at: number; alpha_pct?: number };
export type GradientSpec = { type: "linear" | "radial"; angle_deg: number; cx_pct?: number; cy_pct?: number;
  radius_pct?: number; stops: GradientStop[] };

export type Background =
  | { kind: "colour"; colour: string }
  | ({ kind: "gradient" } & GradientSpec)
  | { kind: "image"; asset_id: string; fit: "cover" | "contain" | "stretch"; dim_pct: number; fallback?: string;
    zoom?: number; focal_x_pct?: number; focal_y_pct?: number; blur_mm?: number };

/** A gradient laid over the background, below the layers; stops carry their own alpha. */
export type Overlay = GradientSpec;

export type Shadow = { dx_mm: number; dy_mm: number; blur_mm: number; colour: string; opacity_pct: number };
export type Outline = { width_mm: number; colour: string };
export type TextStroke = { colour: string; width_pt: number };
export type Highlight = { colour: string; pad_x_mm: number; pad_y_mm: number; radius_mm: number };
export type Underline = { colour: string; thickness_pt: number; offset_pt: number };

/** One run of rich text; unset keys inherit from the layer. */
export type Span = { text: string; font_family?: string; font_weight?: number; colour?: string;
  size_pt?: number | null; size_scale?: number; tracking_pt?: number | null; uppercase?: boolean | null };

export type LayerKind = "text" | "data_field" | "image" | "logo" | "photo" | "desk_qr" | "verify_qr" | "barcode"
  | "shape" | "band" | "perforation" | "icon" | "signature" | "signature_row" | "seal" | "certificate_id";

export type PhotoFilter = "none" | "grey" | "duotone";
export type PolygonShape = "triangle" | "diamond" | "hexagon" | "star";
export type MaskShape = "none" | "rounded" | "circle" | "arch";

export type Layer = {
  id: string; kind: LayerKind; name: string;
  x_mm: number; y_mm: number; w_mm: number; h_mm: number; rotation: number; opacity: number;
  locked: boolean; hidden: boolean;
  /** Layers sharing a group id select and move together (the id names a `side.groups` row in v3). */
  group?: string | null;
  text?: string; field?: string; font_family?: string; font_weight?: number; font_size_pt?: number;
  align?: "left" | "center" | "right"; valign?: "top" | "middle" | "bottom"; colour?: string;
  uppercase?: boolean; tracking_pt?: number; line_height?: number; shrink_to_fit?: boolean;
  /** v3 rich text. `text` stays the concatenation of the spans. */
  spans?: Span[] | null; shadow?: Shadow | null; highlight?: Highlight | null; underline?: Underline | null;
  translations?: Record<string, string> | null;
  asset_id?: string; fit?: "cover" | "contain" | "stretch";
  /** Image and photo framing: zoom 1-4 and the focal point inside the frame. */
  zoom?: number; focal_x_pct?: number; focal_y_pct?: number; flip_x?: boolean; flip_y?: boolean;
  mask?: MaskShape; outline?: Outline | null;
  /** original | cutout (when ready) | auto (the cut-out only when the holder chose it). */ variant?: "original" | "cutout" | "auto";
  /** Logos: space | organisation | event | symbol. Barcodes: number | desk. */
  source?: "space" | "organisation" | "event" | "symbol" | "number" | "desk"; tile?: boolean; show_text?: boolean;
  filter?: PhotoFilter; duotone_dark?: string; duotone_light?: string;
  shape?: "rect" | "ellipse" | "line" | "circle" | "rounded" | "square" | "arch" | PolygonShape;
  /** Barcodes: the symbology (decision 345(c)); absent = Code 128. */
  symbology?: "code128" | "code39" | "ean13" | "upca" | "pdf417" | "datamatrix" | "aztec";
  /** Icon layers: a key of the vendored icon library (studioIcons.json); never path data or a URL. */
  icon?: string;
  /** Shapes: an outline colour. Text layers: a glyph stroke (see `textStroke`). */
  fill?: string | null; stroke?: string | TextStroke | null; stroke_mm?: number; radius_mm?: number;
  fill_gradient?: GradientSpec | null;
  orientation?: "vertical" | "horizontal";
  /** Certificates: a signatory slot (1-3), a row of slots, the seal and the serial. */
  signatory_slot?: number; slots?: number[]; gap_mm?: number; show_image?: boolean; show_name?: boolean;
  show_title?: boolean; rule?: { colour: string; width_pt: number } | null;
  style?: "ring" | "scallop" | "star"; label?: string; ring_text?: string; ring_text_colour?: string;
  format?: "full" | "short";
};

export type LayerGroup = { id: string; name: string; locked: boolean; hidden: boolean };

export type Side = { page_width_mm: number; page_height_mm: number; background: Background; layers: Layer[];
  overlay?: Overlay | null; groups?: LayerGroup[] };

export type Watermark = { kind: "none" | "text" | "image"; text: string; asset_id: string | null; opacity_pct: number;
  angle_deg: number; colour: string };

/** Editor-only guides: never printed by any server output. */
export type PunchSlot = { shape: "slot" | "round"; x_mm: number; y_mm: number; w_mm: number; h_mm: number;
  side: "front" | "back" | "both" };
export type Guides = { bleed_mm: number; safe_mm: number; margin_mm: number; punch_slot: PunchSlot | null;
  rulers: { axis: "x" | "y"; at_mm: number }[] };

export type CardDocument = {
  version: 2 | 3; kind?: "card" | "certificate"; stock: string; page_width_mm?: number; page_height_mm?: number;
  back_enabled: boolean; mono: boolean; watermark: Watermark; guides?: Guides; front: Side; back: Side;
  source?: { kind: string } | null;
};

export type SideName = "front" | "back";

export type CardDomain = "member_cards" | "id_programme" | "event_card" | "event_ticket" | "staff_cards";
/** What the side panels need from a design: a real card design, or a certificate draft that has no design row. */
export type StudioSubject = Pick<CardDesign, "id" | "answer_fields"> & { domain: CardDomain | "certificate" };

export type CardDesign = {
  id: number; makerspace_id?: number; domain: CardDomain; name: string; plan_id: number | null; title_id: number | null;
  programme_id: number | null; organization_id: number | null; event_id: number | null; ticket_type_id: number | null;
  target_label: string; status: "draft" | "pending_approval" | "published"; document: CardDocument; revision: number;
  published_revision: number | null; published_at: string | null; archived_at?: string | null; has_unpublished_changes: boolean;
  pending_approval: CardReview | null; last_review: CardReview | null;
  needs_approval: boolean; can_approve: boolean; can_edit: boolean; updated_at: string;
  /** A programme's printed questions, placeable as {{field:<key>}}. */
  answer_fields?: { key: string; label: string }[];
};

export type CardReview = { id: number; revision: number; decision: "pending" | "approved" | "rejected" | "withdrawn";
  note: string; created_at: string };

export type CardTemplate = { key: string; label: string; theme: "light" | "dark"; document: CardDocument };

export type CardFont = { family: string; category: string; weights: number[]; scripts: string[]; bundled: boolean;
  state: "bundled" | "ready" | "preparing" | "unavailable" | "not_fetched" };
