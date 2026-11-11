// The CardDesignDocument v2 (backend apps/card_designs/layout.py is the authority; it
// normalises every save). Millimetres, top-left origin, z-order = layer list order.

export type Background =
  | { kind: "colour"; colour: string }
  | { kind: "gradient"; type: "linear" | "radial"; angle_deg: number; stops: { colour: string; at: number }[] }
  | { kind: "image"; asset_id: string; fit: "cover" | "contain"; dim_pct: number; fallback?: string };

export type LayerKind = "text" | "data_field" | "image" | "logo" | "photo" | "desk_qr" | "verify_qr" | "barcode"
  | "shape" | "band" | "perforation";

export type PhotoFilter = "none" | "grey" | "duotone";

export type Layer = {
  id: string; kind: LayerKind; name: string;
  x_mm: number; y_mm: number; w_mm: number; h_mm: number; rotation: number; opacity: number;
  locked: boolean; hidden: boolean;
  /** Layers sharing a group id select and move together. */
  group?: string | null;
  text?: string; field?: string; font_family?: string; font_weight?: number; font_size_pt?: number;
  align?: "left" | "center" | "right"; valign?: "top" | "middle" | "bottom"; colour?: string;
  uppercase?: boolean; tracking_pt?: number; line_height?: number; shrink_to_fit?: boolean;
  asset_id?: string; fit?: "cover" | "contain";
  /** Logos: space | organisation | event | symbol. Barcodes: number | desk. */
  source?: "space" | "organisation" | "event" | "symbol" | "number" | "desk"; tile?: boolean; show_text?: boolean;
  filter?: PhotoFilter; duotone_dark?: string; duotone_light?: string;
  shape?: "rect" | "ellipse" | "line" | "circle" | "rounded" | "square";
  fill?: string | null; stroke?: string | null; stroke_mm?: number; radius_mm?: number;
  orientation?: "vertical" | "horizontal";
};

export type Side = { page_width_mm: number; page_height_mm: number; background: Background; layers: Layer[] };

export type Watermark = { kind: "none" | "text" | "image"; text: string; asset_id: string | null; opacity_pct: number;
  angle_deg: number; colour: string };

export type CardDocument = {
  version: 2; stock: string; page_width_mm?: number; page_height_mm?: number; back_enabled: boolean; mono: boolean;
  watermark: Watermark; front: Side; back: Side;
};

export type SideName = "front" | "back";

export type CardDomain = "member_cards" | "id_programme" | "event_card" | "event_ticket";

export type CardDesign = {
  id: number; domain: CardDomain; name: string; plan_id: number | null; title_id: number | null;
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
