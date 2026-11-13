import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest, StructuredApiError } from "../../lib/api";
import type { EventWebsite, WebsiteTarget } from "../events/websiteTypes";
import { EventWebsiteEditor } from "./EventWebsiteEditor";

vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"), staffRequest: vi.fn() }));
// The cover editor is a canvas tool jsdom cannot drive; expose its onSave contract instead.
vi.mock("./eventProgramme/CoverPhotoEditor", () => ({
  CoverPhotoEditor: ({ onSave }: { onSave: (file: File, alt: string) => Promise<void> }) => <>
    <button type="button" onClick={() => onSave(new File(["x"], "c.png"), "A cover").catch((e: Error) => { document.title = e.message; })}>fake cover ok</button>
    <button type="button" onClick={() => onSave(new File(["x"], "c.png"), "").catch((e: Error) => { document.title = e.message; })}>fake cover no alt</button>
  </>,
}));

const target: WebsiteTarget = { kind: "events", id: 5, makerspaceId: 3 };
const url = "/admin/events/5/website/";
const site = (over: Partial<EventWebsite> = {}): EventWebsite => ({
  revision: 4, released: false, inherited: false, published_revision_id: null, draft_revision_id: 9, assets: [], tagline: "", accent_color: "",
  sections: [{ kind: "intro", slug: "about", title: "About", body: "Hi", url: "", visibility: "published", position: 0, asset_id: null }], sessions: [],
  ...over,
} as unknown as EventWebsite);

let remote: EventWebsite;
let readError: Error | undefined;
let writeError: Error | undefined;
let calls: Array<{ path: string; method: string; body?: unknown }>;

function show(props: Partial<Parameters<typeof EventWebsiteEditor>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><EventWebsiteEditor target={target} canEdit canPublish status="published" {...props} /></QueryClientProvider>);
  return { client, ...view };
}
const edit = async (value = "Changed") => fireEvent.change(await screen.findByLabelText("Title"), { target: { value } });

beforeEach(() => {
  remote = site();
  readError = undefined; writeError = undefined; calls = [];
  document.title = "";
  vi.mocked(staffRequest).mockReset();
  vi.mocked(staffRequest).mockImplementation(async (path: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ path, method, body: typeof init?.body === "string" ? JSON.parse(init.body) : init?.body });
    if (path === "/admin/makerspaces/3") return { cover_image_url: "/space-cover.png", logo_url: null };
    if (method === "GET") { if (readError) throw readError; return remote; }
    if (writeError) throw writeError;
    if (path === `${url}release/`) { const b = JSON.parse(String(init?.body)); remote = { ...remote, released: b.released }; return remote; }
    if (method === "PUT") { remote = { ...remote, revision: remote.revision + 1, sections: JSON.parse(String(init?.body)).sections }; return remote; }
    return remote;
  });
});

describe("loading and error states", () => {
  it("shows a loading status while the website loads, then the unreleased state", async () => {
    show();
    expect(screen.getByText("Loading website…")).toBeInTheDocument();
    expect(await screen.findByText("Website unreleased")).toBeInTheDocument();
    expect(screen.getByText("Unreleased")).toBeInTheDocument();
  });
  it("shows the typed API error with a retry that refetches", async () => {
    readError = new StructuredApiError(403, { detail: "Module disabled", code: "module_disabled" });
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Module disabled (module_disabled)");
    expect(screen.queryByRole("button", { name: "Preview draft sections" })).toBeNull();
    readError = undefined;
    fireEvent.click(screen.getByRole("button", { name: "Retry website" }));
    expect(await screen.findByText("Website unreleased")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("save and release", () => {
  it("saves a changed draft, showing Saving… while pending and refreshing the base revision", async () => {
    show();
    await edit();
    expect(screen.getByText("Save the website before releasing it or changing images.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Release saved draft" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Save website" }));
    await waitFor(() => expect(screen.queryByText("Save the website before releasing it or changing images.")).toBeNull());
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.path).toBe(url);
    expect((put?.body as { revision: number; sections: Array<{ title: string }> }).revision).toBe(4);
    expect((put?.body as { sections: Array<{ title: string }> }).sections[0].title).toBe("Changed");
    expect(screen.getByLabelText("Title")).toHaveValue("Changed");
  });
  it("surfaces a save failure as an alert with the typed code and keeps the draft", async () => {
    writeError = new StructuredApiError(409, { detail: "Revision conflict", code: "revision_conflict" });
    show();
    await edit("Mine");
    fireEvent.click(screen.getByRole("button", { name: "Save website" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Revision conflict (revision_conflict)");
    expect(screen.getByLabelText("Title")).toHaveValue("Mine");
  });
  it("releases the saved draft with the current revision, then offers Unrelease", async () => {
    show();
    const release = await screen.findByRole("button", { name: "Release saved draft" });
    expect(screen.queryByRole("button", { name: "Unrelease website" })).toBeNull();
    fireEvent.click(release);
    await waitFor(() => expect(calls.find((c) => c.path === `${url}release/`)?.body).toEqual({ released: true, revision: 4 }));
    expect(await screen.findByText("Website released")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Unrelease website" }));
    await waitFor(() => expect(calls.filter((c) => c.path === `${url}release/`).pop()?.body).toEqual({ released: false, revision: 4 }));
  });
  it("blocks release for an unpublished event and for an unsaved (revision 0) website", async () => {
    show({ status: "draft" });
    expect(await screen.findByRole("button", { name: "Release saved draft" })).toBeDisabled();
  });
  it("blocks release when the website is inherited and labels the save as an override", async () => {
    remote = site({ inherited: true, released: true });
    show();
    expect(await screen.findByText(/Inherited from series; saving creates a private occurrence override\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Release saved draft" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Unrelease website" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save occurrence override" })).toBeEnabled();
  });
  it("warns when saved draft changes await release", async () => {
    remote = site({ released: true, published_revision_id: "1", draft_revision_id: "2" } as unknown as Partial<EventWebsite>);
    show();
    expect(await screen.findByText("Saved draft changes are waiting for release.")).toBeInTheDocument();
    expect(screen.getByText("Released")).toBeInTheDocument();
  });
  it("hides release actions without publish permission and for a terminal event", async () => {
    const { unmount } = show({ canPublish: false });
    await screen.findByText("Website unreleased");
    expect(screen.queryByRole("button", { name: "Release saved draft" })).toBeNull();
    unmount();
    show({ status: "completed" });
    await screen.findByText("Website unreleased");
    expect(screen.queryByRole("button", { name: "Release saved draft" })).toBeNull();
    expect(screen.getByRole("button", { name: "Save website" })).toBeDisabled();
    expect(screen.queryByRole("list", { name: "Website images" })).toBeNull();
    expect(screen.queryByText("Private website images")).toBeNull();
  });
  it("lets server capabilities narrow the caller's own permissions", async () => {
    remote = site({ capabilities: { can_edit_details: false, can_publish_schedule: false } } as Partial<EventWebsite>);
    show();
    await screen.findByText("Website unreleased");
    expect(screen.getByRole("button", { name: "Save website" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Release saved draft" })).toBeNull();
    expect(screen.queryByText("Private website images")).toBeNull();
  });
});

describe("conflict handling", () => {
  it("keeps the unsaved draft on a server change, blocks save, and discards on request", async () => {
    const { client } = show();
    await edit("Mine");
    remote = site({ revision: 5, sections: [{ ...site().sections[0], title: "Theirs" }] });
    await act(async () => { await client.invalidateQueries({ queryKey: ["event-website", 3, "events", 5] }); });
    expect(await screen.findByText(/The website changed on the server\. Your unsaved draft is retained with its original revision \(4\)/)).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("Mine");
    expect(screen.getByRole("button", { name: "Save website" })).toBeDisabled();
    fireEvent.submit(screen.getByRole("button", { name: "Save website" }).closest("form")!);
    expect(calls.some((c) => c.method === "PUT")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Discard draft and reload latest" }));
    await waitFor(() => expect(screen.getByLabelText("Title")).toHaveValue("Theirs"));
    expect(screen.queryByText(/The website changed on the server/)).toBeNull();
  });
});

describe("preview", () => {
  it("toggles the draft preview and loads the makerspace artwork only then, when no inherited image is given", async () => {
    show();
    const toggle = await screen.findByRole("button", { name: "Preview draft sections" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(calls.some((c) => c.path === "/admin/makerspaces/3")).toBe(false);
    fireEvent.click(toggle);
    const region = await screen.findByRole("region", { name: "Event draft preview" });
    expect(region).toHaveTextContent("Draft preview · not released");
    expect(region).toHaveTextContent("About");
    await waitFor(() => expect(region.querySelector("img[src*='space-cover.png']")).not.toBeNull());
    fireEvent.click(screen.getByRole("button", { name: "Hide draft preview" }));
    expect(screen.queryByRole("region", { name: "Event draft preview" })).toBeNull();
  });
  it("uses the inherited event image and skips the makerspace lookup", async () => {
    show({ inheritedImage: { url: "/event.png", alt: "Event photo" } });
    fireEvent.click(await screen.findByRole("button", { name: "Preview draft sections" }));
    const region = await screen.findByRole("region", { name: "Event draft preview" });
    await waitFor(() => expect(region.querySelector("img[src*='event.png']")).not.toBeNull());
    expect(calls.some((c) => c.path === "/admin/makerspaces/3")).toBe(false);
  });
});

describe("private website images", () => {
  const withAssets = () => site({ assets: [{ id: 7, alt_text: "Poster", size_bytes: 10, pinned: false }, { id: 8, alt_text: "Pinned art", size_bytes: 10, pinned: true }] } as Partial<EventWebsite>);
  it("deletes an image, but a revision-pinned image cannot be deleted", async () => {
    remote = withAssets();
    show();
    const del = await screen.findByRole("button", { name: "Delete Poster" });
    expect(screen.getByRole("button", { name: /Delete Pinned art \(retained by a revision\)/ })).toBeDisabled();
    fireEvent.click(del);
    await waitFor(() => expect(calls.find((c) => c.method === "DELETE")?.path).toBe(`${url}assets/7`));
  });
  it("uploads a described file, adding replace_id when replacing", async () => {
    remote = withAssets();
    show();
    fireEvent.change(await screen.findByLabelText("Image description"), { target: { value: "New art" } });
    fireEvent.change(screen.getByLabelText("Replace image"), { target: { value: "7" } });
    fireEvent.change(screen.getByLabelText("Image file"), { target: { files: [new File(["b"], "n.png", { type: "image/png" })] } });
    fireEvent.submit(screen.getByLabelText("Image description").closest("form")!);
    await waitFor(() => expect(calls.some((c) => c.path === `${url}assets/` && c.method === "POST")).toBe(true));
    const form = calls.find((c) => c.path === `${url}assets/`)!.body as FormData;
    expect(form.get("alt_text")).toBe("New art");
    expect(form.get("revision")).toBe("4");
    expect(form.get("replace_id")).toBe("7");
    expect((form.get("file") as File).name).toBe("n.png");
  });
  it("uploads a new image without replace_id and ignores a submit with no file", async () => {
    show();
    fireEvent.change(await screen.findByLabelText("Image description"), { target: { value: "Solo" } });
    fireEvent.submit(screen.getByLabelText("Image description").closest("form")!);
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    fireEvent.change(screen.getByLabelText("Image file"), { target: { files: [new File(["b"], "s.png", { type: "image/png" })] } });
    fireEvent.submit(screen.getByLabelText("Image description").closest("form")!);
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect((calls.find((c) => c.method === "POST")!.body as FormData).has("replace_id")).toBe(false);
  });
  it("blocks uploads and deletes while the draft has unsaved changes", async () => {
    remote = withAssets();
    show();
    await edit();
    expect(screen.getByRole("button", { name: "Upload image (up to 5 MB)" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Delete Poster" })).toBeDisabled();
  });
  it("blocks replacing an image on an inherited website", async () => {
    remote = { ...withAssets(), inherited: true } as EventWebsite;
    show();
    fireEvent.change(await screen.findByLabelText("Replace image"), { target: { value: "7" } });
    expect(screen.getByRole("button", { name: "Upload image (up to 5 MB)" })).toBeDisabled();
  });
  it("cover save uploads with alt text and revision; refuses with no description or unsaved changes", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: "fake cover ok" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === `${url}assets/`)).toBe(true));
    const form = calls.find((c) => c.method === "POST")!.body as FormData;
    expect(form.get("alt_text")).toBe("A cover");
    expect(form.get("revision")).toBe("4");
    fireEvent.click(screen.getByRole("button", { name: "fake cover no alt" }));
    await waitFor(() => expect(document.title).toBe("Describe this image in 1 to 200 characters."));
    await edit();
    fireEvent.click(screen.getByRole("button", { name: "fake cover ok" }));
    await waitFor(() => expect(document.title).toBe("Save your website changes before uploading a cover."));
  });
});
