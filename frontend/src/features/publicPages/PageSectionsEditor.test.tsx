import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { emptyDocument, newSection } from "./documentDefaults";
import { PageSectionsEditor } from "./PageSectionsEditor";
import type { PageAsset, PageDocument, PageOwner, PageSection, SectionType } from "./pageTypes";

const assets = [{ id: 4, alt_text: "Workshop photo" }, { id: 5, alt_text: "Team photo" }] as unknown as PageAsset[];
const ALL: SectionType[] = ["about", "gallery", "team", "upcoming_events", "stats", "testimonials", "links", "location", "linked_makerspaces", "organization_events",
  "functional_content", "membership_plans", "sponsors", "shop", "crew"];
let latest: PageDocument;

function Harness({ initial, ...props }: { initial: PageSection[]; allowed?: SectionType[]; required?: SectionType[]; maxSections?: number; kind?: PageOwner["kind"] | "event"; disabled?: boolean; assets?: PageAsset[] }) {
  const [document, setDocument] = useState<PageDocument>({ ...emptyDocument(), sections: initial });
  latest = document;
  return <MemoryRouter><PageSectionsEditor document={document} assets={props.assets ?? assets} allowed={props.allowed ?? ALL} required={props.required ?? []}
    maxSections={props.maxSections} kind={props.kind ?? "makerspace"} disabled={props.disabled ?? false} onChange={setDocument} /></MemoryRouter>;
}
const section = <K extends SectionType>(type: K, payload: Partial<Extract<PageSection, { type: K }>["payload"]> = {}): PageSection => {
  const base = newSection(type);
  return { ...base, payload: { ...base.payload, ...payload } } as PageSection;
};
const show = (initial: PageSection[], props: Omit<Parameters<typeof Harness>[0], "initial"> = {}) => render(<Harness initial={initial} {...props} />);

describe("section list controls", () => {
  it("moves a section up and down, announces it, and disables the edge arrows", () => {
    show([section("about", { title: "First" }), section("stats", { title: "Second" })]);
    expect(screen.getByRole("button", { name: "Move About up" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move Public stats down" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Move About down" }));
    expect(latest.sections.map((row) => row.type)).toEqual(["stats", "about"]);
    expect(screen.getByRole("status")).toHaveTextContent("About moved to position 2 of 2.");
    fireEvent.click(screen.getByRole("button", { name: "Move About up" }));
    expect(latest.sections.map((row) => row.type)).toEqual(["about", "stats"]);
  });
  it("toggles a section on and off", () => {
    show([section("about")]);
    const toggle = screen.getAllByRole("checkbox")[0];
    expect(toggle).toBeChecked();
    fireEvent.click(toggle);
    expect(latest.sections[0].enabled).toBe(false);
  });
  it("removes a section and announces how many remain", () => {
    show([section("about"), section("stats")]);
    fireEvent.click(screen.getByRole("button", { name: "Remove About" }));
    expect(latest.sections.map((row) => row.type)).toEqual(["stats"]);
    expect(screen.getByRole("status")).toHaveTextContent("About removed. 1 sections remain.");
  });
  it("a required group cannot be disabled or removed", () => {
    show([section("functional_content")], { required: ["functional_content"] });
    expect(screen.getByRole("button", { name: "Remove Tools, spaces and activities" })).toBeDisabled();
    expect(screen.getAllByRole("checkbox")[0]).toBeDisabled();
  });
  it("preserves an unknown section type read-only with an explanation", () => {
    show([{ id: "u1", type: "hologram", enabled: true, payload: {} } as unknown as PageSection]);
    expect(screen.getByText("This section is preserved when you save. Use a newer editor to change its fields.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove section" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move section up" })).toBeDisabled();
    expect(screen.getAllByRole("checkbox")[0]).toBeDisabled();
  });
  it("disables every control while read-only", () => {
    show([section("about"), section("stats")], { disabled: true });
    expect(screen.getByRole("button", { name: "Move About down" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Remove About" })).toBeDisabled();
    expect(screen.getByLabelText("New section")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Add section" })).toBeDisabled();
  });
});

describe("adding sections", () => {
  it("offers only allowed, labelled types still under their per-type limit (about may appear twice)", () => {
    show([section("about"), section("shop")], { allowed: ["about", "shop", "crew", "hologram" as SectionType] });
    const options = within(screen.getByLabelText("New section")).getAllByRole("option").map((option) => option.textContent);
    expect(options).toEqual(["Choose a section", "About", "Crew"]);
  });
  it("hides about after two and shows no add until a type is chosen", () => {
    show([section("about"), section("about")], { allowed: ["about", "crew"] });
    expect(within(screen.getByLabelText("New section")).queryByRole("option", { name: "About" })).toBeNull();
    expect(screen.getByRole("button", { name: "Add section" })).toBeDisabled();
  });
  it("adds the chosen section with its defaults, resets the picker and announces the position", () => {
    show([section("about")]);
    fireEvent.change(screen.getByLabelText("New section"), { target: { value: "crew" } });
    fireEvent.click(screen.getByRole("button", { name: "Add section" }));
    expect(latest.sections.map((row) => row.type)).toEqual(["about", "crew"]);
    expect(latest.sections[1]).toMatchObject({ enabled: true, payload: { title: "" } });
    expect(screen.getByRole("status")).toHaveTextContent("Crew added at position 2.");
    expect(screen.getByLabelText("New section")).toHaveValue("");
  });
  it("stops adding at the owner's section limit", () => {
    show([section("about"), section("stats")], { maxSections: 2 });
    fireEvent.change(screen.getByLabelText("New section"), { target: { value: "crew" } });
    expect(screen.getByRole("button", { name: "Add section" })).toBeDisabled();
  });
});

describe("section forms", () => {
  it("about: edits the title and story", () => {
    show([section("about")]);
    fireEvent.change(screen.getByLabelText("Section title"), { target: { value: "Our story" } });
    fireEvent.change(screen.getByLabelText("Story"), { target: { value: "We build." } });
    expect(latest.sections[0].payload).toMatchObject({ title: "Our story", markdown: "We build." });
  });
  it("functional content is explanatory only (no title field)", () => {
    show([section("functional_content")]);
    expect(screen.getByText(/The overview links to Inventory and shows enabled activities/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Section title")).toBeNull();
  });
  it("collection sections explain they refresh live; shop and crew say what they show", () => {
    show([section("upcoming_events"), section("shop"), section("crew")]);
    expect(screen.getAllByText(/This collection is refreshed from eligible public records on every read/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/Shows a few public products from your shop/)).toBeInTheDocument();
    expect(screen.getByText(/Shows approved crew who chose to appear publicly/)).toBeInTheDocument();
  });
  it("stats: a makerspace owns three metrics, an organization only the event count", () => {
    const { unmount } = show([section("stats")]);
    expect(screen.getAllByRole("checkbox")).toHaveLength(4);
    fireEvent.click(screen.getByLabelText("Publish public event count"));
    expect(latest.sections[0].payload).toMatchObject({ show_published_event_count: true });
    unmount();
    show([section("stats")], { kind: "organization" });
    expect(screen.queryByLabelText("Publish the exact-count inventory subset")).toBeNull();
    expect(screen.getByLabelText("Publish public event count")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Consent to publish the active public member aggregate/)).toBeNull();
  });
  it("location: toggles public consent, switches source, and edits entered fields", () => {
    show([section("location", { source: "entered" })]);
    fireEvent.click(screen.getByLabelText(/Publish this/));
    expect(latest.sections[0].payload).toMatchObject({ enabled_publicly: true });
    fireEvent.change(screen.getByLabelText("Public address"), { target: { value: "1 Forge Lane" } });
    fireEvent.change(screen.getByLabelText("HTTPS map link"), { target: { value: "https://maps.test/x" } });
    fireEvent.change(screen.getByLabelText("Public latitude"), { target: { value: "9.9" } });
    fireEvent.change(screen.getByLabelText("Public longitude"), { target: { value: "76.2" } });
    fireEvent.change(screen.getByLabelText("Directions"), { target: { value: "Second floor" } });
    expect(latest.sections[0].payload).toMatchObject({ address: "1 Forge Lane", map_url: "https://maps.test/x", latitude: 9.9, longitude: 76.2, directions: "Second floor" });
    fireEvent.change(screen.getByLabelText("Location source"), { target: { value: "makerspace_public" } });
    expect(latest.sections[0].payload).toMatchObject({ source: "makerspace_public" });
    expect(screen.queryByLabelText("Public address")).toBeNull();
  });
  it("location: an organization cannot pick the makerspace's location", () => {
    show([section("location")], { kind: "organization" });
    expect(screen.queryByRole("option", { name: "Existing public makerspace location" })).toBeNull();
    expect(screen.getByRole("option", { name: "Enter a public address" })).toBeInTheDocument();
  });
  it("sponsors show their help link", () => {
    show([section("sponsors")]);
    expect(screen.getAllByText(/refreshed from eligible public records/).length).toBeGreaterThan(0);
  });
});

describe("entry forms", () => {
  it("gallery: add (disabled without assets), pick an image, caption, remove", () => {
    const { unmount } = show([section("gallery")], { assets: [] });
    expect(screen.getByRole("button", { name: "Add gallery image" })).toBeDisabled();
    unmount();
    show([section("gallery")]);
    fireEvent.click(screen.getByRole("button", { name: "Add gallery image" }));
    expect(latest.sections[0].payload).toMatchObject({ items: [{ asset_id: 4, caption: "" }] });
    fireEvent.change(screen.getByLabelText("Gallery image 1"), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText("Caption"), { target: { value: "Open day" } });
    expect(latest.sections[0].payload).toMatchObject({ items: [{ asset_id: 5, caption: "Open day" }] });
    fireEvent.click(screen.getByRole("button", { name: "Remove image 1" }));
    expect(latest.sections[0].payload).toMatchObject({ items: [] });
  });
  it("testimonials: add, edit quote and attribution, remove", () => {
    show([section("testimonials")]);
    fireEvent.click(screen.getByRole("button", { name: "Add testimonial" }));
    fireEvent.change(screen.getByLabelText("Quote 1"), { target: { value: "Great space" } });
    fireEvent.change(screen.getByLabelText("Attribution"), { target: { value: "Asha" } });
    expect(latest.sections[0].payload).toMatchObject({ entries: [{ quote: "Great space", attribution: "Asha" }] });
    fireEvent.click(screen.getByRole("button", { name: "Remove quote 1" }));
    expect(latest.sections[0].payload).toMatchObject({ entries: [] });
  });
  it("links: add, edit label, platform and URL, remove", () => {
    show([section("links")]);
    fireEvent.click(screen.getByRole("button", { name: "Add link" }));
    fireEvent.change(screen.getByLabelText("Link label 1"), { target: { value: "Code" } });
    fireEvent.change(screen.getByLabelText("Platform"), { target: { value: "github" } });
    fireEvent.change(screen.getByLabelText("HTTPS URL"), { target: { value: "https://github.com/x" } });
    expect(latest.sections[0].payload).toMatchObject({ entries: [{ label: "Code", platform: "github", url: "https://github.com/x" }] });
    fireEvent.click(screen.getByRole("button", { name: "Remove link 1" }));
    expect(latest.sections[0].payload).toMatchObject({ entries: [] });
  });
  it("team: switches a person between explicit and linked member, and edits each shape", () => {
    show([section("team")]);
    fireEvent.click(screen.getByRole("button", { name: /Add person/ }));
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Ravi" } });
    fireEvent.change(screen.getByLabelText("HTTPS profile link"), { target: { value: "https://r.test" } });
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "Lead" } });
    expect(latest.sections[0].payload).toMatchObject({ entries: [{ kind: "explicit", display_name: "Ravi", url: "https://r.test", role: "Lead" }] });
    fireEvent.change(screen.getByLabelText("Person 1"), { target: { value: "member" } });
    expect(latest.sections[0].payload).toMatchObject({ entries: [{ kind: "member", profile_id: 0, role: "Lead" }] });
    fireEvent.change(screen.getByLabelText("Member profile ID"), { target: { value: "12" } });
    expect(latest.sections[0].payload).toMatchObject({ entries: [{ kind: "member", profile_id: 12 }] });
    fireEvent.change(screen.getByLabelText("Person 1"), { target: { value: "explicit" } });
    expect(latest.sections[0].payload).toMatchObject({ entries: [{ kind: "explicit", display_name: "" }] });
    fireEvent.click(screen.getByRole("button", { name: "Remove person 1" }));
    expect(latest.sections[0].payload).toMatchObject({ entries: [] });
  });
  it.each([
    ["testimonials", "Add testimonial", 20, (i: number) => ({ id: `e${i}`, quote: "q", attribution: "a" })],
    ["links", "Add link", 20, (i: number) => ({ id: `e${i}`, label: "l", platform: "website" })],
    ["team", "Add person", 40, (i: number) => ({ id: `e${i}`, kind: "explicit", display_name: "n", role: "r" })],
    ["gallery", "Add gallery image", 24, (i: number) => ({ asset_id: 4, caption: `c${i}` })],
  ] as const)("the %s add button stops at its limit of %i entries", (type, label, limit, make) => {
    const key = type === "gallery" ? "items" : "entries";
    const full = section(type, { [key]: Array.from({ length: limit }, (_, n) => make(n)) } as never);
    const { unmount } = show([full]);
    expect(screen.getByRole("button", { name: label })).toBeDisabled();
    unmount();
    const room = section(type, { [key]: Array.from({ length: limit - 1 }, (_, n) => make(n)) } as never);
    show([room]);
    expect(screen.getByRole("button", { name: label })).toBeEnabled();
  });
  it("a link or person with no URL shows an empty URL field", () => {
    show([section("links", { entries: [{ id: "l1", label: "Code", platform: "website" }] } as never)]);
    expect(screen.getByLabelText("HTTPS URL")).toHaveValue("");
  });
});

describe("stable callbacks", () => {
  it("does not call onChange on render", () => {
    const onChange = vi.fn();
    render(<MemoryRouter><PageSectionsEditor document={{ ...emptyDocument(), sections: [section("about")] }} assets={assets} allowed={ALL} required={[]} kind="makerspace" disabled={false} onChange={onChange} /></MemoryRouter>);
    expect(onChange).not.toHaveBeenCalled();
  });
});
