import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest, StructuredApiError } from "../../lib/api";
import { bookingWebsiteKey } from "../bookings/bookingWebsiteApi";
import type { BookingWebsite } from "../bookings/bookingWebsiteTypes";
import { BookingWebsiteEditor } from "./BookingWebsiteEditor";
import type { BookableSpace } from "./bookingsApi";

vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"), staffRequest: vi.fn() }));
const space = { id: 8, makerspace_id: 3, is_public: true, is_active: true, can_manage_grants: true } as BookableSpace;
const website = (revision: number, title = "Original", released = false): BookingWebsite => ({ revision, released, assets: [], sections: [
  { kind: "rules", slug: "rules", title, body: "Booking rules", url: "", visibility: "published", position: 0, asset_id: null },
] });
let remote: BookingWebsite;
let readError: Error | undefined;
let writes: BookingWebsite[];
const base = "/admin/spaces/8/website/";

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><BookingWebsiteEditor space={space} /></QueryClientProvider>);
  return { client, ...view };
}
async function refetch(client: QueryClient) {
  await act(async () => { await client.invalidateQueries({ queryKey: bookingWebsiteKey(3, 8) }); });
}
async function editTitle(title = "Unsaved draft") {
  fireEvent.change(await screen.findByLabelText("Section title"), { target: { value: title } });
}
beforeEach(() => {
  remote = website(1);
  readError = undefined;
  writes = [];
  vi.mocked(staffRequest).mockReset();
  vi.mocked(staffRequest).mockImplementation(async (path, init) => {
    if (init?.method === "PUT") {
      const input = JSON.parse(String(init.body)) as BookingWebsite;
      writes.push(input);
      if (input.revision !== remote.revision) throw new StructuredApiError(409, { detail: "Website revision conflict. Reload before saving." });
      remote = { ...remote, sections: input.sections, revision: remote.revision + 1 };
      return remote;
    }
    if (path === base || path === "/admin/spaces/9/website/") {
      if (readError) throw readError;
      return remote;
    }
    throw new Error(`Unexpected request: ${path}`);
  });
});

describe("booking website drafts", () => {
  it.each(["content", "image", "release"])("preserves the draft and original revision after another operator's %s change", async (change) => {
    const { client } = show();
    await editTitle();
    remote = website(2, "Other operator", change === "release");
    if (change === "image") remote.assets = [{ id: 9, alt_text: "New image", size_bytes: 123 }];
    await refetch(client);
    expect(screen.getByLabelText("Section title")).toHaveValue("Unsaved draft");
    expect(screen.getByRole("button", { name: "Release website" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Save content" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Website revision conflict");
    expect(writes[0]).toMatchObject({ revision: 1, sections: [{ title: "Unsaved draft" }] });
    expect(screen.getByLabelText("Section title")).toHaveValue("Unsaved draft");
    fireEvent.click(screen.getByRole("button", { name: "Reload website (discard draft)" }));
    await waitFor(() => expect(screen.getByLabelText("Section title")).toHaveValue("Other operator"));
    await editTitle("Rebased draft");
    fireEvent.click(screen.getByRole("button", { name: "Save content" }));
    await waitFor(() => expect(writes[1]?.revision).toBe(2));
  });

  it("adopts the saved revision after success so the next edit can save", async () => {
    show();
    await editTitle("First save");
    fireEvent.click(screen.getByRole("button", { name: "Save content" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Release website" })).toBeEnabled());
    await editTitle("Second save");
    fireEvent.click(screen.getByRole("button", { name: "Save content" }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes.map((row) => row.revision)).toEqual([1, 2]);
    await waitFor(() => expect(screen.getByRole("button", { name: "Release website" })).toBeEnabled());
  });

  it("preserves a draft when a background refetch fails", async () => {
    const { client } = show();
    await editTitle();
    readError = new Error("Website unavailable");
    await refetch(client);
    expect(await screen.findByRole("alert")).toHaveTextContent("Website unavailable");
    expect(screen.getByLabelText("Section title")).toHaveValue("Unsaved draft");
    readError = undefined;
    await refetch(client);
    expect(screen.getByLabelText("Section title")).toHaveValue("Unsaved draft");
  });

  it("starts a separate draft when the resource changes", async () => {
    const { client, rerender } = show();
    await editTitle();
    client.setQueryData(bookingWebsiteKey(3, 9), website(5, "Another resource"));
    rerender(<QueryClientProvider client={client}><BookingWebsiteEditor space={{ ...space, id: 9 }} /></QueryClientProvider>);
    expect(screen.getByLabelText("Section title")).toHaveValue("Another resource");
  });
});
