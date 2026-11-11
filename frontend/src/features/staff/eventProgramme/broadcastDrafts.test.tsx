import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { BroadcastComposer } from "./BroadcastComposer";
import { EventBroadcastsPanel } from "./EventBroadcastsPanel";
import { draftStatusText } from "./broadcastAutosave";
import type { BroadcastCampaign } from "./broadcastApi";
vi.mock("../../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../../lib/api")>(), staffRequest: vi.fn() }));
const draft: BroadcastCampaign = { id: 7, version: 3, subject: "Welcome", body: "Hello", statuses: ["registered"], attendance: "any", status: "draft", available_at: null, render_schema_version: 2, design: "classic", ctas: [] };
const mount = (element: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{element}</QueryClientProvider>);
beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

it("words the autosave line the way Events does", () => {
  const idle = { saving: false, failed: false, conflict: false, savedAt: null };
  expect(draftStatusText(idle, false, false)).toBe("Changes are saved as a draft automatically.");
  expect(draftStatusText(idle, true, true)).toBe("Unsaved changes");
  expect(draftStatusText({ ...idle, saving: true }, true, true)).toBe("Saving…");
  expect(draftStatusText({ ...idle, failed: true }, true, true)).toBe("Couldn't save");
  expect(draftStatusText({ ...idle, savedAt: "2026-11-11T10:00:00Z" }, false, true)).toMatch(/^Draft saved · /);
});

it("opens the author's own draft by itself", async () => {
  vi.mocked(staffRequest).mockImplementation(async path => String(path).includes("broadcasts/?page=") ? { count: 1, next: null, previous: null, results: [draft] } : []);
  mount(<EventBroadcastsPanel makerspaceId={9} eventId={42} />);
  expect(await screen.findByDisplayValue("Welcome")).toBeInTheDocument();
  expect(screen.getByText("Draft saved")).toBeInTheDocument();
});

it("asks before discarding, then deletes the saved draft and starts empty", async () => {
  vi.mocked(staffRequest).mockResolvedValue(undefined);
  const discarded = vi.fn();
  mount(<BroadcastComposer makerspaceId={9} eventId={42} existing={draft} onSaved={() => {}} onDiscarded={discarded} />);
  fireEvent.click(screen.getByRole("button", { name: "Discard draft…" }));
  expect(await screen.findByText("Discard this draft?")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Discard draft" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/events/42/broadcasts/7/", { method: "DELETE" }));
  await waitFor(() => expect(screen.getByLabelText("Subject")).toHaveValue(""));
  expect(discarded).toHaveBeenCalled();
});

it("formats the message from the toolbar into the safe subset", () => {
  vi.mocked(staffRequest).mockRejectedValue(new Error("off"));
  mount(<BroadcastComposer makerspaceId={9} eventId={42} onSaved={() => {}} />);
  const message = screen.getByLabelText("Message") as HTMLTextAreaElement;
  fireEvent.change(message, { target: { value: "Doors open" } });
  message.setSelectionRange(0, 10);
  fireEvent.click(screen.getByRole("button", { name: "Heading" }));
  expect(message).toHaveValue("## Doors open");
  fireEvent.click(screen.getByRole("button", { name: "Link" }));
  fireEvent.change(screen.getByLabelText("Link text"), { target: { value: "Your ticket" } });
  fireEvent.change(screen.getByLabelText("Link destination"), { target: { value: "{{ ticket_url }}" } });
  fireEvent.click(screen.getByRole("button", { name: "Add link" }));
  expect(message.value).toContain("[Your ticket]({{ ticket_url }})");
});
