import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import { PageEditorAssets } from "./PageEditorAssets";
import { PageHandleForm } from "./PageHandleForm";
import { PageRevisionHistory } from "./PageRevisionHistory";
import { editorBase } from "./pageApi";
import { editorFixture } from "./pageFixtures";
import type { EditorState, PageOwner } from "./pageTypes";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: request }));
vi.mock("./PageImage", () => ({ PageImage: ({ url, alt, token }: { url: string; alt: string; token: string }) => <img src={url} alt={alt} data-token={token} /> }));

const owner: PageOwner = { kind: "makerspace", id: 7 };
const wrap = (ui: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{ui}</QueryClientProvider>);
const withAssets = (over: Partial<EditorState> = {}): EditorState => editorFixture({ assets: [
  { id: 1, alt_text: "Front door", pinned: false, preview_url: "/p/1" }, { id: 2, alt_text: "Old logo", pinned: true, preview_url: "/p/2" }] as never, ...over });

beforeEach(() => request.mockReset());

describe("PageHandleForm", () => {
  it("describes a claimed handle and offers rename and release; release is passed up with the version", () => {
    const run = vi.fn();
    wrap(<PageHandleForm state={editorFixture({ version: 5, handle: "forge" })} owner={owner} disabled={false} run={run} />);
    expect(screen.getByText(/Current handle: \/forge\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rename handle" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Release handle and unpublish" }));
    expect(run).toHaveBeenCalledWith({ action: "release_handle", version: 5 });
  });
  it("says Not claimed and offers claim, with no release button", () => {
    wrap(<PageHandleForm state={editorFixture({ handle: null } as Partial<EditorState>)} owner={owner} disabled={false} run={vi.fn()} />);
    expect(screen.getByText(/Current handle: Not claimed\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Claim handle" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Release handle and unpublish" })).toBeNull();
  });
  it("lowercases the typed handle, validates the pattern, and claims with the lowercased value", () => {
    const run = vi.fn();
    wrap(<PageHandleForm state={editorFixture({ version: 3, handle: null } as Partial<EditorState>)} owner={owner} disabled={false} run={run} />);
    const input = screen.getByLabelText("Handle");
    fireEvent.change(input, { target: { value: "-Bad" } });
    expect(screen.getByRole("button", { name: "Claim handle" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Check availability" })).toBeDisabled();
    fireEvent.change(input, { target: { value: "Maker-Hub" } });
    expect(input).toHaveValue("maker-hub");
    fireEvent.click(screen.getByRole("button", { name: "Claim handle" }));
    expect(run).toHaveBeenCalledWith({ action: "handle", version: 3, handle: "maker-hub" });
  });
  it("does not submit while disabled", () => {
    const run = vi.fn();
    wrap(<PageHandleForm state={editorFixture({ handle: null } as Partial<EditorState>)} owner={owner} disabled run={run} />);
    fireEvent.submit(screen.getByLabelText("Handle").closest("form")!);
    expect(run).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Check availability" })).toBeDisabled();
  });
  it("checks availability against the owner's endpoint and shows the answer, clearing it when the handle changes", async () => {
    request.mockResolvedValue({ handle: "maker-hub", available: true });
    wrap(<PageHandleForm state={editorFixture({ handle: null } as Partial<EditorState>)} owner={owner} disabled={false} run={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Handle"), { target: { value: "maker-hub" } });
    fireEvent.click(screen.getByRole("button", { name: "Check availability" }));
    expect(await screen.findByRole("status")).toHaveTextContent("/maker-hub is available. Claiming checks availability again.");
    expect(request).toHaveBeenCalledWith(`${editorBase(owner)}handle-availability/?handle=maker-hub`, { cache: "no-store" });
    fireEvent.change(screen.getByLabelText("Handle"), { target: { value: "maker-hub2" } });
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  });
  it("says unavailable for a taken handle and shows a typed error when the check fails", async () => {
    request.mockResolvedValueOnce({ handle: "taken", available: false });
    wrap(<PageHandleForm state={editorFixture({ handle: null } as Partial<EditorState>)} owner={owner} disabled={false} run={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Handle"), { target: { value: "taken" } });
    fireEvent.click(screen.getByRole("button", { name: "Check availability" }));
    expect(await screen.findByRole("status")).toHaveTextContent("/taken is unavailable.");
    request.mockRejectedValueOnce(new StructuredApiError(429, { detail: "Slow down", code: "throttled" }));
    fireEvent.change(screen.getByLabelText("Handle"), { target: { value: "other" } });
    fireEvent.click(screen.getByRole("button", { name: "Check availability" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Slow down");
  });
});

describe("PageEditorAssets", () => {
  const file = (size = 10, type = "image/png") => { const f = new File(["x"], "a.png", { type }); Object.defineProperty(f, "size", { value: size }); return f; };
  const pick = (value: File) => fireEvent.change(screen.getByLabelText("JPEG, PNG or WebP image"), { target: { files: [value] } });

  it("lists images with their pin state and deletes an unpinned one against the current version", () => {
    const run = vi.fn();
    wrap(<PageEditorAssets state={withAssets({ version: 4 })} pending={false} dirty={false} run={run} />);
    expect(screen.getByText("Old logo · Retained by a revision")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Front door" })).toHaveAttribute("data-token", "4");
    expect(screen.getByRole("button", { name: "Delete Old logo" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Delete Front door" }));
    expect(run).toHaveBeenCalledWith({ action: "delete_asset", version: 4, id: 1 });
  });
  it("uploads a described file with the version and alt text", () => {
    const run = vi.fn();
    wrap(<PageEditorAssets state={withAssets({ version: 4 })} pending={false} dirty={false} run={run} />);
    const upload = screen.getByRole("button", { name: "Upload image" });
    expect(upload).toBeDisabled();
    const picked = file();
    pick(picked);
    fireEvent.change(screen.getByLabelText("Image description"), { target: { value: "Entrance" } });
    expect(upload).toBeEnabled();
    fireEvent.submit(upload.closest("form")!);
    expect(run).toHaveBeenCalledWith({ action: "upload", version: 4, file: picked, alt_text: "Entrance" });
  });
  it("refuses a file above the upload limit with the byte count and does not upload", () => {
    const run = vi.fn();
    wrap(<PageEditorAssets state={withAssets()} pending={false} dirty={false} run={run} />);
    pick(file(6_000_000));
    fireEvent.change(screen.getByLabelText("Image description"), { target: { value: "Huge" } });
    fireEvent.submit(screen.getByRole("button", { name: "Upload image" }).closest("form")!);
    expect(screen.getByRole("alert")).toHaveTextContent(/Choose an image smaller than 5,000,000 bytes\./);
    expect(run).not.toHaveBeenCalled();
  });
  it("blocks uploads at the image-count limit and when the remaining storage is too small", () => {
    const base = editorFixture();
    const { unmount } = wrap(<PageEditorAssets state={withAssets({ limits: { ...base.limits, assets: 2 } })} pending={false} dirty={false} run={vi.fn()} />);
    pick(file());
    fireEvent.change(screen.getByLabelText("Image description"), { target: { value: "x" } });
    expect(screen.getByRole("button", { name: "Upload image" })).toBeDisabled();
    unmount();
    wrap(<PageEditorAssets state={withAssets({ limits: { ...base.limits, storage_bytes: 100, storage_bytes_used: 95 } })} pending={false} dirty={false} run={vi.fn()} />);
    pick(file(50));
    fireEvent.change(screen.getByLabelText("Image description"), { target: { value: "x" } });
    expect(screen.getByRole("button", { name: "Upload image" })).toBeDisabled();
  });
  it("disables everything while pending, dirty, or without edit rights", () => {
    const states: Array<[boolean, boolean, EditorState]> = [
      [true, false, withAssets()], [false, true, withAssets()],
      [false, false, { ...withAssets(), capabilities: { ...withAssets().capabilities, can_edit_details: false } }],
    ];
    for (const [pending, dirty, state] of states) {
      const { unmount } = wrap(<PageEditorAssets state={state} pending={pending} dirty={dirty} run={vi.fn()} />);
      expect(screen.getByLabelText("Image description")).toBeDisabled();
      expect(screen.getByRole("button", { name: "Delete Front door" })).toBeDisabled();
      unmount();
    }
  });
  it("resets the form when the page version changes", () => {
    const { rerender } = render(<QueryClientProvider client={new QueryClient()}><PageEditorAssets state={withAssets({ version: 4 })} pending={false} dirty={false} run={vi.fn()} /></QueryClientProvider>);
    fireEvent.change(screen.getByLabelText("Image description"), { target: { value: "Draft alt" } });
    rerender(<QueryClientProvider client={new QueryClient()}><PageEditorAssets state={withAssets({ version: 5 })} pending={false} dirty={false} run={vi.fn()} /></QueryClientProvider>);
    expect(screen.getByLabelText("Image description")).toHaveValue("");
  });
  it("ignores a submit with no file chosen", () => {
    const run = vi.fn();
    wrap(<PageEditorAssets state={withAssets()} pending={false} dirty={false} run={run} />);
    fireEvent.submit(screen.getByRole("button", { name: "Upload image" }).closest("form")!);
    expect(run).not.toHaveBeenCalled();
  });
});

describe("PageRevisionHistory", () => {
  const rows = [
    { id: "r1", created_at: "2026-11-01T10:00:00Z", created_by_display: "Asha", summary: { section_types: ["about", "stats"] } },
    { id: "r2", created_at: "2026-10-01T10:00:00Z", created_by_display: null, summary: { section_types: [] } },
  ];
  it("loads nothing until opened, then lists revisions with editor, sections and fallbacks", async () => {
    request.mockResolvedValue({ count: 2, next: null, previous: null, results: rows });
    wrap(<PageRevisionHistory owner={owner} />);
    expect(request).not.toHaveBeenCalled();
    const toggle = screen.getByRole("button", { name: "Show revision history" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(await screen.findByText(/Asha/)).toBeInTheDocument();
    expect(screen.getByText("About, Public stats")).toBeInTheDocument();
    expect(screen.getByText(/Former editor/)).toBeInTheDocument();
    expect(screen.getByText("No sections")).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith(`${editorBase(owner)}revisions/?page=1`, { cache: "no-store" });
    fireEvent.click(screen.getByRole("button", { name: "Hide revision history" }));
    expect(screen.queryByText("Asha")).toBeNull();
  });
  it("says there are no saved revisions when the list is empty", async () => {
    request.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    wrap(<PageRevisionHistory owner={owner} />);
    fireEvent.click(screen.getByRole("button", { name: "Show revision history" }));
    expect(await screen.findByText("No saved revisions yet.")).toBeInTheDocument();
  });
  it("shows a load error with a retry that recovers", async () => {
    request.mockRejectedValueOnce(new Error("History down")).mockResolvedValue({ count: 1, next: null, previous: null, results: [rows[0]] });
    wrap(<PageRevisionHistory owner={owner} />);
    fireEvent.click(screen.getByRole("button", { name: "Show revision history" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load history.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/Asha/)).toBeInTheDocument();
  });
  it("pages through revisions", async () => {
    request.mockImplementation(async (path = "") => ({ count: 30, next: null, previous: null, results: [{ ...rows[0], id: path.includes("page=2") ? "p2" : "p1", created_by_display: path.includes("page=2") ? "Second page editor" : "First page editor" }] }));
    wrap(<PageRevisionHistory owner={owner} />);
    fireEvent.click(screen.getByRole("button", { name: "Show revision history" }));
    expect(await screen.findByText(/First page editor/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(await screen.findByText(/Second page editor/)).toBeInTheDocument();
  });
});
