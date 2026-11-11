import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { StructuredApiError } from "../../../lib/api/errors";
import { ChatTemplatesSection } from "./ChatTemplatesSection";

vi.mock("../../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results });
const template = { id: 4, feature: "hardware_requests", event: "request_created", text_body: "New request {{ id }}", is_active: true,
  updated_at: "2026-11-01T10:00:00Z" };
const BASE = "/admin/platform/spaces/2/chat-templates";

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ChatTemplatesSection /></QueryClientProvider>);
}

async function chooseSpace() {
  const select = await screen.findByRole("combobox", { name: "Space" });
  await screen.findByRole("option", { name: "North Lab" });
  fireEvent.change(select, { target: { value: "2" } });
}

describe("ChatTemplatesSection", () => {
  beforeEach(() => {
    request.mockReset();
    request.mockImplementation(async (path, init) => {
      if (path.startsWith("/admin/platform/space-health")) return page([{ id: 2, name: "North Lab" }]) as never;
      if (init?.method === "POST") throw new StructuredApiError(400, { event: ["Unknown event."] });
      if (init?.method === "DELETE") return undefined as never;
      return page([template]) as never;
    });
  });

  it("lists a space's templates and deletes one back to the built-in text", async () => {
    renderSection();
    await chooseSpace();
    expect(await screen.findByText("hardware_requests · request_created")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete the request_created template" }));
    expect(screen.getByText(/goes back to the built-in text/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete template" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith(`${BASE}/4`, { method: "DELETE" }, "platform"));
  });

  it("shows a server refusal under the event field", async () => {
    renderSection();
    await chooseSpace();
    fireEvent.click(await screen.findByRole("button", { name: "New template" }));
    const form = screen.getByRole("form", { name: "New chat template" });
    fireEvent.change(screen.getAllByRole("textbox", { name: "Feature" })[0], { target: { value: "hardware_requests" } });
    fireEvent.change(screen.getAllByRole("textbox", { name: "Event" })[0], { target: { value: "nope" } });
    fireEvent.change(screen.getAllByRole("textbox", { name: "Message" })[0], { target: { value: "Hi" } });
    fireEvent.submit(form);
    expect(await screen.findByText("Unknown event.")).toBeInTheDocument();
  });
});
