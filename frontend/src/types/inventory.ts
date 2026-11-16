export type Availability =
  | null
  | {
      mode: "status_only" | "exact_count";
      // "Lent at events only": an event-only item (decision 221b) shows no count and no stock status.
      label?: "Available" | "Limited" | "Unavailable" | "Lent at events only";
      count?: number;
    };

export type Product = {
  id: number;
  name: string;
  description: string;
  borrowing_terms?: string;
  category_id?: number | null;
  category_name?: string | null;
  category_slug?: string | null;
  tracking_mode?: "quantity" | "individual";
  availability: Availability;
  image_url?: string | null;
  // Lane L12: when the item is out and its expected-back date is published ("YYYY-MM-DD").
  expected_back_on?: string | null;
  /** Decision 221b: lent only through an event, so the catalogue offers no request button. */
  event_only?: boolean;
};

export type PublicCategory = {
  id: number;
  name: string;
  slug: string;
  display_order: number;
  icon: string;
  product_count: number;
};

export type Makerspace = {
  name: string;
  public_code: string;
  slug: string;
  location: string;
  map_url?: string;
  logo_url?: string | null;
  cover_image_url?: string | null;
  /** Public directory only (decision 275 change); hand-typed until `generated/api.ts` is regenerated. */
  offers?: PublicSpaceOffer[];
  next_event?: PublicNextEvent | null;
};

/** What a public space offers, in the server's order (inventory/public_offers.py). */
export type PublicSpaceOffer = "inventory" | "machines" | "events" | "bookings" | "shop" | "memberships" | "donations";
/** The space's next public event; `public_url` is a relative app path. */
export type PublicNextEvent = { title: string; starts_at: string; public_url: string };

export type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type RequestCartItem = {
  productId: number;
  name: string;
  quantity: number;
};

export type RequestSubmitResponse = {
  public_token: string;
  status: string;
};

export type PublicToolLoan = {
  public_token: string;
  status: string;
  items: {
    product_name: string;
    quantity: number;
  }[];
};

