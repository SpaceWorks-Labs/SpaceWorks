import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MachineTypeGuide, type GuideMoment } from "./MachineTypeGuide";

const { memberRequest } = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", async importOriginal => ({ ...(await importOriginal<object>()), memberRequest }));

const guide = { machine_type_id: 9, machine_type_name: "Laser", training_notes: "Wear eye protection.", notes_at_session_start: true, notes_at_job_request: false,
  documents: [{ id: 4, title: "Laser manual", content_type: "application/pdf", size_bytes: 1000 }] };
const show = (when?: GuideMoment) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MachineTypeGuide makerspaceId={1} typeId={9} when={when} /></QueryClientProvider>);
const asked = () => memberRequest.mock.calls.length;

describe("MachineTypeGuide", () => {
  beforeEach(() => { memberRequest.mockReset(); });

  it("renders nothing while the type has no notes and no documents", async () => {
    memberRequest.mockResolvedValue({ ...guide, training_notes: "  ", documents: [] });
    const { container } = show();
    await waitFor(() => expect(asked()).toBe(1));
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing for a refusal such as a non-member", async () => {
    memberRequest.mockRejectedValue(new Error("forbidden"));
    const { container } = show();
    await waitFor(() => expect(asked()).toBe(1));
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the notes and opens a document through its signed link", async () => {
    const open = vi.spyOn(window, "open").mockReturnValue(null);
    memberRequest.mockImplementation(async (path: string) => path.endsWith("/url") ? { url: "https://signed.test/laser" } : guide);
    show();
    expect(await screen.findByText("Before you use it")).toBeVisible();
    expect(screen.getByText("Wear eye protection.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Laser manual" }));
    await waitFor(() => expect(open).toHaveBeenCalledWith("https://signed.test/laser", "_blank", "noopener,noreferrer"));
    expect(memberRequest).toHaveBeenCalledWith("/member/machine-type-documents/4/url");
    open.mockRestore();
  });

  it("follows the space's choice of where to show it", async () => {
    memberRequest.mockResolvedValue(guide);
    const { container, unmount } = show("job_request");
    await waitFor(() => expect(asked()).toBe(1));
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(container).toBeEmptyDOMElement();
    unmount();
    show("session_start");
    expect(await screen.findByText("Wear eye protection.")).toBeVisible();
  });
});
