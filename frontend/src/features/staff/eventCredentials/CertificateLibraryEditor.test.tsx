import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { LayerDocument } from "./layout";
import { CertificateLibraryEditor } from "./CertificateLibraryEditor";

const request = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
const base = "/admin/makerspaces/1/event-certificate-library/5/";
const document = { version: 2, page_width_mm: 297, page_height_mm: 210, layers: [] } as LayerDocument;
const fetchMock = vi.fn();

beforeEach(() => {
  request.mockReset();
  fetchMock.mockReset().mockResolvedValue({ ok: true });
  vi.stubGlobal("fetch", fetchMock);
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === base && !init) return { id: 5, name: "Workshop", version: 3, archived: false };
    if (path === `${base}artwork/`) return { id: 11, upload_url: "https://storage.test/put", headers: { "Content-Type": "image/png" } };
    if (path === `${base}artwork/11/finalize/`) return { id: 11, resource_id: "abc" };
    if (path === base && init?.method === "PATCH") return { id: 5, version: 4 };
    throw new Error(`Unexpected ${path}`);
  });
});
afterEach(() => { vi.unstubAllGlobals(); });

it("uploads template-owned artwork and saves a renamed revision with the current version", async () => {
  render(<QueryClientProvider client={new QueryClient()}><CertificateLibraryEditor makerspaceId={1} templateId={5} document={document} /></QueryClientProvider>);
  const nameField = await screen.findByLabelText("Library template name");
  expect(nameField).toHaveValue("Workshop");
  fireEvent.change(nameField, { target: { value: "Workshop 2027" } });
  const file = new File(["png"], "bg.png", { type: "image/png" });
  fireEvent.change(screen.getByLabelText("Background artwork for this template"), { target: { files: [file] } });
  expect(await screen.findByText("Artwork ready. It is used when you save the next revision.")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith("https://storage.test/put", { method: "PUT", headers: { "Content-Type": "image/png" }, body: file });
  fireEvent.click(screen.getByRole("button", { name: "Save draft layout as a new template revision" }));
  await waitFor(() => expect(request.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(true));
  const patch = request.mock.calls.find(([, init]) => init?.method === "PATCH")!;
  expect(JSON.parse(patch[1].body)).toMatchObject({ name: "Workshop 2027", expected_version: 3, artwork_id: 11, parameters: document });
});
