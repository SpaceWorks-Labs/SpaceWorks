import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PublicEventWebsite, WebsiteProgramme, WebsiteSectionCard, type WebsiteLinks } from "./PublicEventWebsite";
import type { PublicEventWebsiteData, WebsiteSection, WebsiteSession } from "./websiteTypes";

const section = (over: Partial<WebsiteSection>): WebsiteSection => ({ kind: "intro", slug: "s", title: "Title", body: "", url: "", visibility: "published", position: 0, asset_id: null, ...over } as WebsiteSection);
const session = (over: Partial<WebsiteSession>): WebsiteSession => ({ slug: "talk", title: "Opening talk", body: "", visibility: "published", starts_at: "2026-12-01T10:00:00Z", ends_at: "2026-12-01T11:00:00Z", track: "main", room: "r1", speakers: ["ada"], ...over } as WebsiteSession);
const site = (over: Record<string, unknown> = {}) => ({ revision: 1, released: true, sections: [], sessions: [], assets: [], ...over }) as unknown as PublicEventWebsiteData;
const links: WebsiteLinks = { schedule: "/s", speaker: (slug) => `/speaker/${slug}`, session: (slug) => `/session/${slug}` };

describe("WebsiteSectionCard", () => {
  it("shows a highlight icon, an image through the renderer, and a safe link only", () => {
    render(<WebsiteSectionCard row={section({ kind: "highlight", icon: "*", title: "Big day", image_url: "/i.png", image_alt_text: "Crowd", url: "https://x.test/a", body: "Hello" })}
      image={(url, alt) => <span data-testid="img">{url}|{alt}</span>} />);
    expect(screen.getByRole("heading", { name: "Big day" })).toBeInTheDocument();
    expect(screen.getByTestId("img")).toHaveTextContent("/i.png|Crowd");
    expect(screen.getByRole("link", { name: "Visit Big day" })).toHaveAttribute("href", "https://x.test/a");
  });
  it("falls back to a plain img (alt = title) and hides an unsafe link", () => {
    render(<WebsiteSectionCard row={section({ title: "Plain", image_url: "/p.png", url: "javascript:alert(1)" })} />);
    expect(screen.getByRole("img", { name: "Plain" })).toHaveAttribute("src", "/p.png");
    expect(screen.queryByRole("link")).toBeNull();
  });
  it("links a speaker title and lists only the safe social links", () => {
    render(<WebsiteSectionCard links={links} row={section({ kind: "speaker", slug: "ada", title: "Ada", headline: "Engineer", organization: "Lab",
      website_url: "https://ada.test", linkedin_url: "ftp://no", x_url: "https://x.com/ada" })} />);
    expect(screen.getByRole("link", { name: "Ada" })).toHaveAttribute("href", "/speaker/ada");
    expect(screen.getByText("Engineer")).toBeInTheDocument();
    expect(screen.getByText("Lab")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Website" })).toHaveAttribute("href", "https://ada.test");
    expect(screen.getByRole("link", { name: "X" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "LinkedIn" })).toBeNull();
  });
  it("renders a speaker title as plain text without links", () => {
    render(<WebsiteSectionCard row={section({ kind: "speaker", title: "Ada" })} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByRole("heading", { name: "Ada" })).toBeInTheDocument();
  });
});

describe("WebsiteProgramme", () => {
  it("lists only published sessions, with delay note and linked speakers", () => {
    render(<WebsiteProgramme links={links} website={site({ sections: [section({ slug: "main", title: "Main stage" }), section({ slug: "r1", title: "Room 1" })] })}
      sessions={[session({ effective_starts_at: "2026-12-01T10:15:00Z", effective_ends_at: "2026-12-01T11:15:00Z" }), session({ slug: "hidden", title: "Hidden", visibility: "draft" })]} />);
    expect(screen.getByRole("link", { name: "Opening talk" })).toHaveAttribute("href", "/session/talk");
    expect(screen.queryByText("Hidden")).toBeNull();
    expect(screen.getByText(/Planned start:/)).toBeInTheDocument();
    expect(screen.getByText("Main stage · Room 1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ada" })).toHaveAttribute("href", "/speaker/ada");
    expect(screen.getByRole("link", { name: "Full schedule" })).toHaveAttribute("href", "/s");
  });
  it("shows plain titles and no schedule link without links; no planned-start note when on time", () => {
    render(<WebsiteProgramme website={site()} sessions={[session({ speakers: undefined, effective_starts_at: "2026-12-01T10:00:00Z" })]} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.queryByText(/Planned start:/)).toBeNull();
    expect(screen.getByRole("heading", { name: "Opening talk" })).toBeInTheDocument();
  });
});

describe("PublicEventWebsite", () => {
  it("renders the hero cover and tagline through the default image renderer, and groups sections", () => {
    render(<PublicEventWebsite website={site({ tagline: "Make things", cover: { url: "/c.png", alt: "Cover art" },
      sections: [section({ kind: "intro", slug: "a", title: "About us" }), section({ kind: "faq", slug: "f", title: "Q1" }), section({ kind: "intro", slug: "d", title: "Draft", visibility: "draft" })] })} />);
    const root = screen.getByLabelText("Event website");
    expect(within(root).getByRole("img", { name: "Cover art" })).toHaveAttribute("src", "/c.png");
    expect(within(root).getByText("Make things")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "About" })).getByRole("heading", { name: "About us" })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "FAQ" })).getByRole("heading", { name: "Q1" })).toBeInTheDocument();
    expect(screen.queryByText("Draft")).toBeNull();
  });
  it("uses a custom image renderer for the cover", () => {
    render(<PublicEventWebsite website={site({ cover: { url: "/c.png", alt: "Cover art" } })} image={(u, a) => <b data-testid="custom">{u}:{a}</b>} />);
    expect(screen.getByTestId("custom")).toHaveTextContent("/c.png:Cover art");
  });
  it("groups sponsors by tier in tier order and omits empty tiers", () => {
    render(<PublicEventWebsite website={site({ sections: [
      section({ kind: "sponsor", slug: "g", title: "GoldCo", sponsor_tier: "gold" }), section({ kind: "sponsor", slug: "n", title: "NoTier" }),
    ] })} />);
    const sponsors = screen.getByRole("region", { name: "Sponsors" });
    expect(within(sponsors).getByRole("region", { name: "Gold sponsors" })).toHaveTextContent("GoldCo");
    expect(within(sponsors).getByRole("region", { name: "Community partner sponsors" })).toHaveTextContent("NoTier");
    expect(within(sponsors).queryByRole("region", { name: "Platinum sponsors" })).toBeNull();
  });
  it("renders the schedule with tracks and programme, but nothing when only drafts exist", () => {
    const { unmount } = render(<PublicEventWebsite website={site({ sections: [section({ kind: "track", slug: "main", title: "Main stage" })], sessions: [session({})] })} />);
    const schedule = screen.getByRole("region", { name: "Schedule" });
    expect(within(schedule).getByRole("region", { name: "Tracks" })).toBeInTheDocument();
    expect(within(schedule).getByRole("region", { name: "Programme" })).toBeInTheDocument();
    unmount();
    render(<PublicEventWebsite website={site({ sessions: [session({ visibility: "draft" })] })} />);
    expect(screen.queryByRole("region", { name: "Schedule" })).toBeNull();
  });
  it("renders only the programme when there are sessions but no tracks", () => {
    render(<PublicEventWebsite website={site({ sessions: [session({})] })} />);
    expect(screen.queryByRole("region", { name: "Tracks" })).toBeNull();
    expect(screen.getByRole("region", { name: "Programme" })).toBeInTheDocument();
  });
  it("renders a venue with coordinates, a safe map link and each filled note, plus room cards", () => {
    render(<PublicEventWebsite website={site({ venue: { name: "Hall", address: "1 Road", city: "Kochi", country: "IN", latitude: 9.9, longitude: 76.2,
      map_url: "https://maps.test/x", directions: "Turn left", parking: "", public_transport: "Bus 4", accessibility_notes: "" },
    sections: [section({ kind: "room", slug: "r1", title: "Room 1" })] })} />);
    const venue = screen.getByRole("region", { name: "Venue" });
    expect(within(venue).getByRole("heading", { name: "Hall" })).toBeInTheDocument();
    expect(within(venue).getByText("1 Road, Kochi, IN")).toBeInTheDocument();
    expect(within(venue).getByText(/Coordinates: 9\.9/)).toBeInTheDocument();
    expect(within(venue).getByRole("link", { name: "View venue map" })).toHaveAttribute("href", "https://maps.test/x");
    expect(within(venue).getByRole("heading", { name: "Directions" })).toBeInTheDocument();
    expect(within(venue).getByRole("heading", { name: "Public transport" })).toBeInTheDocument();
    expect(within(venue).queryByRole("heading", { name: "Parking" })).toBeNull();
    expect(within(venue).getByRole("heading", { name: "Room 1" })).toBeInTheDocument();
  });
  it("omits coordinates and map link when absent", () => {
    render(<PublicEventWebsite website={site({ venue: { name: "Hall", address: "", city: "", country: "", latitude: null, longitude: null, map_url: "ftp://bad" } })} />);
    expect(screen.queryByText(/Coordinates/)).toBeNull();
    expect(screen.queryByRole("link", { name: "View venue map" })).toBeNull();
  });
  it("hides a disabled group and honours section_order", () => {
    render(<PublicEventWebsite website={site({ section_order: ["FAQ"], section_enabled: { ABOUT: false },
      sections: [section({ kind: "intro", slug: "a", title: "About us" }), section({ kind: "faq", slug: "f", title: "Q1" })] })} />);
    expect(screen.queryByRole("region", { name: "About" })).toBeNull();
    expect(screen.getByRole("region", { name: "FAQ" })).toBeInTheDocument();
  });
  it("renders nothing for the editorial group without a document", () => {
    render(<PublicEventWebsite website={site({ section_order: ["EDITORIAL"] })} />);
    expect(screen.getByLabelText("Event website")).toBeEmptyDOMElement();
  });
  it("applies an accent colour as the page style", () => {
    render(<PublicEventWebsite website={site({ accent_color: "#aa0000" })} />);
    expect(screen.getByLabelText("Event website").getAttribute("style")).toBeTruthy();
  });
});
