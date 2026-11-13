import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import { PublicPageBuilder } from "./PublicPageBuilder";
import { editorBase, editorKey } from "./pageApi";
import { editorFixture } from "./pageFixtures";
import type { EditorState, PageOwner } from "./pageTypes";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: request }));
// The section, presentation, handle, asset, revision and preview editors have their own tests. Stubs here expose
// only what the builder owns: the dirty document, the version it saves against and the operations it runs.
vi.mock("./PagePresentationForm", () => ({ PagePresentationForm: ({ document, onChange, disabled }: { document: { accent_choice: string }; onChange: (d: unknown) => void; disabled: boolean }) =>
  <button type="button" disabled={disabled} onClick={() => onChange({ ...document, accent_choice: "edited" })}>edit presentation ({document.accent_choice})</button> }));
vi.mock("./PageSectionsEditor", () => ({ PageSectionsEditor: ({ maxSections, kind }: { maxSections: number; kind: string }) => <p>sections editor kind={kind} max={maxSections}</p> }));
vi.mock("./PageHandleForm", () => ({ PageHandleForm: ({ disabled, run, state }: { disabled: boolean; run: (i: unknown) => void; state: EditorState }) =>
  <button type="button" disabled={disabled} onClick={() => run({ action: "handle", version: state.version, handle: "new" })}>claim handle</button> }));
vi.mock("./PagePreview", () => ({ PagePreview: ({ page }: { page: { title: string } }) => <p>preview of {page.title}</p> }));
vi.mock("./PageEditorAssets", () => ({ PageEditorAssets: ({ dirty, pending }: { dirty: boolean; pending: boolean }) => <p>assets dirty={String(dirty)} pending={String(pending)}</p> }));
vi.mock("./PageRevisionHistory", () => ({ PageRevisionHistory: () => <p>revision history</p> }));

const owner: PageOwner = { kind: "makerspace", id: 7 };
const base = editorBase(owner);
let remote: EditorState;
let readError: Error | undefined;
let writeError: Error | undefined;
let writes: Array<{ path: string; method: string; body: Record<string, unknown> }>;

function mount(who: PageOwner = owner) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><PublicPageBuilder owner={who} /></QueryClientProvider>);
  return { client, ...view };
}
const edit = async () => fireEvent.click(await screen.findByRole("button", { name: /edit presentation/ }));

beforeEach(() => {
  remote = editorFixture();
  readError = undefined; writeError = undefined; writes = [];
  request.mockReset();
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method === "GET") { if (readError) throw readError; return remote; }
    writes.push({ path, method, body: init?.body ? JSON.parse(String(init.body)) : {} });
    if (writeError) throw writeError;
    if (path === `${base}preview/`) return { title: "Forge preview", sections: [] };
    if (path === `${base}publish/`) { remote = { ...remote, version: remote.version + 1, published_revision_id: remote.draft_revision_id }; return remote; }
    if (path === `${base}unpublish/`) { remote = { ...remote, version: remote.version + 1, published_revision_id: null }; return remote; }
    if (method === "PUT" && path === base) { remote = { ...remote, version: remote.version + 1, document: JSON.parse(String(init?.body)).document, draft_revision_id: "10000000-0000-4000-8000-000000000009" }; return remote; }
    remote = { ...remote, version: remote.version + 1 };
    return remote;
  });
});

describe("loading, forbidden and error states", () => {
  it("shows the loader, then the builder with its status pill and guidance", async () => {
    mount();
    expect(screen.getByText("Loading public page builder…")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Public page builder" })).toBeInTheDocument();
    expect(screen.getByText("Draft changes pending")).toBeInTheDocument();
    expect(screen.getByText("sections editor kind=makerspace max=" + editorFixture().limits.sections)).toBeInTheDocument();
    expect(screen.getByText("revision history")).toBeInTheDocument();
    expect(screen.queryByText("Save changes before publishing, claiming a handle or uploading images.")).toBeNull();
  });
  it("tells a non-manager of a makerspace who may edit", async () => {
    readError = new StructuredApiError(403, { detail: "no", code: "forbidden" });
    mount();
    expect(await screen.findByText("Only this makerspace's Space Manager can edit the public page.")).toBeInTheDocument();
  });
  it("tells a non-manager of an organization who may edit", async () => {
    readError = new StructuredApiError(403, { detail: "no", code: "forbidden" });
    mount({ kind: "organization", id: 3 });
    expect(await screen.findByText("Only this organization's profile managers can edit the public page.")).toBeInTheDocument();
  });
  it("shows other load errors with a retry that reloads the builder", async () => {
    readError = new Error("Page service down");
    mount();
    expect(await screen.findByText(/Page service down/)).toBeInTheDocument();
    readError = undefined;
    fireEvent.click(screen.getByRole("button", { name: /retry|try again/i }));
    expect(await screen.findByRole("heading", { name: "Public page builder" })).toBeInTheDocument();
  });
});

describe("status pill and publish gates", () => {
  it("reads Unpublished with no published revision, and the Unpublish button is absent", async () => {
    remote = editorFixture({ published_revision_id: null });
    mount();
    expect(await screen.findByText("Unpublished")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Unpublish page" })).toBeNull();
    expect(screen.getByRole("button", { name: "Publish saved draft" })).toBeEnabled();
  });
  it("reads Draft changes pending when the draft is newer than the published one", async () => {
    remote = editorFixture({ published_revision_id: "10000000-0000-4000-8000-000000000003" });
    mount();
    expect(await screen.findByText("Draft changes pending")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publish saved draft" })).toBeEnabled();
  });
  it("disables publish when the current draft is already published", async () => {
    remote = editorFixture({ draft_revision_id: "same", published_revision_id: "same" });
    mount();
    expect(await screen.findByRole("button", { name: "Publish saved draft" })).toBeDisabled();
  });
  it("disables publish without a handle, with a claim-a-handle hint, and without a saved draft", async () => {
    remote = editorFixture({ handle: null, draft_revision_id: null, published_revision_id: null } as Partial<EditorState>);
    mount();
    expect(await screen.findByText("Claim a handle before publishing.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publish saved draft" })).toBeDisabled();
  });
  it("disables publish and edit for a viewer without the publish/edit capabilities", async () => {
    remote = editorFixture();
    remote = { ...remote, capabilities: { ...remote.capabilities, can_publish: false, can_edit_details: false } };
    mount();
    expect(await screen.findByRole("button", { name: "Publish saved draft" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Validate and preview draft" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "edit presentation (inherit)" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Unpublish page" })).toBeDisabled();
  });
});

describe("saving, previewing and publishing", () => {
  it("saves the edited document against the base version and reports the draft message", async () => {
    mount();
    await edit();
    expect(screen.getByText("Save changes before publishing, claiming a handle or uploading images.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publish saved draft" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "claim handle" })).toBeDisabled();
    expect(screen.getByText("assets dirty=true pending=false")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("Draft saved. Your published page stays unchanged until you publish.")).toBeInTheDocument();
    expect(writes[0]).toMatchObject({ path: base, method: "PUT" });
    expect(writes[0].body).toMatchObject({ version: 2, document: { accent_choice: "edited" } });
    await waitFor(() => expect(screen.queryByText("Save changes before publishing, claiming a handle or uploading images.")).toBeNull());
  });
  it("previews the draft (still a draft) and clears the preview on the next edit", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Validate and preview draft" }));
    expect(await screen.findByText("preview of Forge preview")).toBeInTheDocument();
    expect(screen.getByText("Preview validated. This is still a draft.")).toBeInTheDocument();
    expect(writes[0]).toMatchObject({ path: `${base}preview/`, method: "POST" });
    fireEvent.click(screen.getByRole("button", { name: /edit presentation/ }));
    expect(screen.queryByText("preview of Forge preview")).toBeNull();
    expect(screen.queryByText("Preview validated. This is still a draft.")).toBeNull();
  });
  it("publishes the saved draft revision and says so", async () => {
    remote = editorFixture({ published_revision_id: null });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Publish saved draft" }));
    expect(await screen.findByText("Latest saved draft published.")).toBeInTheDocument();
    expect(writes[0]).toMatchObject({ path: `${base}publish/`, method: "POST", body: { version: 2, draft_revision_id: "10000000-0000-4000-8000-000000000001" } });
    expect(await screen.findByText("Published")).toBeInTheDocument();
  });
  it("unpublishes and keeps the draft", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Unpublish page" }));
    expect(await screen.findByText("Page unpublished. Your draft and history are retained.")).toBeInTheDocument();
    expect(writes[0]).toMatchObject({ path: `${base}unpublish/`, method: "POST", body: { version: 2 } });
  });
  it("any other operation reports that settings were updated", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "claim handle" }));
    expect(await screen.findByText("Page settings updated.")).toBeInTheDocument();
    expect(writes[0]).toMatchObject({ path: `${base}handle/`, method: "PUT", body: { handle: "new" } });
  });
  it("shows a typed operation error and keeps the edits", async () => {
    writeError = new StructuredApiError(422, { detail: "Too many sections", code: "section_limit" });
    mount();
    await edit();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText(/Too many sections/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "edit presentation (edited)" })).toBeInTheDocument();
  });
  it("shows Saving draft… while the save is in flight", async () => {
    let release: (value: unknown) => void = () => undefined;
    mount();
    await edit();
    request.mockImplementation(() => new Promise((resolve) => { release = resolve; }));
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByRole("button", { name: "Saving draft…" })).toBeDisabled();
    release(remote);
  });
  it("ignores a submit while the editor is read-only", async () => {
    remote = { ...editorFixture(), capabilities: { ...editorFixture().capabilities, can_edit_details: false } };
    mount();
    fireEvent.submit((await screen.findByRole("button", { name: "Save draft" })).closest("form")!);
    expect(writes).toHaveLength(0);
  });
});

describe("version conflicts", () => {
  it("keeps local edits on a server version change, blocks save and lets the editor discard or reapply", async () => {
    const { client } = mount();
    await edit();
    remote = editorFixture({ version: 3 });
    await act(async () => { await client.invalidateQueries({ queryKey: editorKey(owner) }); });
    expect(await screen.findByRole("alert")).toHaveTextContent("The server version changed. Your local edits are retained.");
    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Validate and preview draft" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "edit presentation (edited)" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reapply local edits for review" }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(screen.getByRole("button", { name: "edit presentation (edited)" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(writes[0].body).toMatchObject({ version: 3 }));
  });
  it("discarding reloads the saved version", async () => {
    const { client } = mount();
    await edit();
    remote = editorFixture({ version: 3 });
    await act(async () => { await client.invalidateQueries({ queryKey: editorKey(owner) }); });
    fireEvent.click(await screen.findByRole("button", { name: "Discard edits and reload" }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(screen.getByRole("button", { name: "edit presentation (inherit)" })).toBeInTheDocument();
  });
  it("a stale_version rejection raises the conflict alert and refetches", async () => {
    writeError = new StructuredApiError(409, { detail: "Stale", code: "stale_version" });
    mount();
    await edit();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText(/The server version changed. Your local edits are retained/)).toBeInTheDocument();
    expect(request.mock.calls.filter(([, init]) => !init?.method || init.method === "GET").length).toBeGreaterThanOrEqual(2);
  });
});
