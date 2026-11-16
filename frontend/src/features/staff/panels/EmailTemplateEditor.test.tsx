import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { EmailTemplateEditor } from "./EmailTemplateEditor";
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
const detail = { stream: "hardware", audience: "members", key: "accepted", label: "Request accepted", is_active: true,
  is_overridden: false, can_edit_space_default: true, overridable_types: [], description: "Sent after approval.",
  fields: [{ name: "requester", description: "Borrower name" }], subject: "Ready", text_body: "Hello", html_body: "",
  default_subject: "Ready", default_text: "Hello", default_html: "" };
beforeEach(() => {
  request.mockReset();
  request.mockImplementation((url: string) => url.endsWith("/preview") ? Promise.resolve({ subject: "Ready", text_body: "Hello", html_body: "" }) : Promise.resolve(detail));
});
function open() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <MemoryRouter initialEntries={["/admin/email-templates?template=hardware:members:accepted"]}>
      <EmailTemplateEditor makerspaceId={7} selected={{ stream: "hardware", audience: "members", key: "accepted", machineType: null, canEditSpaceDefault: true, overridableTypes: [] }} onSelectMachineType={() => {}} />
    </MemoryRouter>
  </QueryClientProvider>);
}
it("inserts merge fields in the focused body and discards without saving", async () => {
  open();
  const body = await screen.findByRole("textbox", { name: "Plain text body" });
  await waitFor(() => expect(body).toHaveValue("Hello"));
  fireEvent.focus(body);
  fireEvent.click(screen.getByRole("button", { name: "requester" }));
  expect((body as HTMLTextAreaElement).value).toContain("{{ requester }}");
  fireEvent.click(screen.getByRole("button", { name: "Discard" }));
  expect(body).toHaveValue("Hello");
  expect(request.mock.calls.filter(call => call[1]?.method === "PATCH")).toHaveLength(0);
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
});
it("shows a standard retry for failed previews", async () => {
  request.mockImplementation((url: string) => url.endsWith("/preview") ? Promise.reject(new Error("Renderer unavailable")) : Promise.resolve(detail));
  open();
  await screen.findByRole("textbox", { name: "Subject" });
  fireEvent.click(screen.getByRole("button", { name: "Preview" }));
  const retry = await screen.findByRole("button", { name: "Retry" });
  request.mockImplementation((url: string) => url.endsWith("/preview") ? Promise.resolve({ subject: "Rendered", text_body: "Hello", html_body: "" }) : Promise.resolve(detail));
  fireEvent.click(retry);
  expect(await screen.findByText("Rendered")).toBeInTheDocument();
});
