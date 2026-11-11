import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { EmailTemplatesPanel } from "./EmailTemplatesPanel";
import type { Makerspace } from "./shared";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
vi.mock("./EmailTemplateEditor", () => ({ EmailTemplateEditor: ({ onBack }: { onBack: () => void }) =>
  <div><h1>Template editor</h1><button onClick={onBack}>All templates</button></div> }));
function Location() { return <output data-testid="location">{useLocation().search}</output>; }
const template = { stream: "hardware", audience: "members", key: "accepted", label: "Request accepted",
  is_active: true, is_overridden: false, can_edit_space_default: true, overridable_types: [] };
beforeEach(() => { request.mockReset(); request.mockResolvedValue([template]); });
function open(url = "/admin/email-templates") {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[url]}><EmailTemplatesPanel makerspace={{ id: 7, name: "Community Lab" } as Makerspace} /><Location /></MemoryRouter>
  </QueryClientProvider>);
}
it("opens the template editor through the documented query parameter and returns to its index", async () => {
  open();
  fireEvent.click(await screen.findByRole("button", { name: /request accepted/i }));
  expect(await screen.findByRole("heading", { name: "Template editor" })).toBeInTheDocument();
  expect(screen.getByTestId("location")).toHaveTextContent("template=hardware%3Amembers%3Aaccepted");
  fireEvent.click(screen.getByRole("button", { name: "All templates" }));
  expect(await screen.findByRole("heading", { name: "Email templates" })).toBeInTheDocument();
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
});
it("restores a template editor from a deep link", async () => {
  open("/admin/email-templates?template=hardware:members:accepted");
  expect(await screen.findByRole("heading", { name: "Template editor" })).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith("/admin/makerspace/7/email-templates");
});
