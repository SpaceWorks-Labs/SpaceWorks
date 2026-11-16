import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api/errors";
import { OnboardingSection, SELF_HOST_NOTE } from "./OnboardingSection";
import type { HostingRequestDetail } from "./onboardingApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest, publicV1Request: vi.fn() }));

const REQUEST: HostingRequestDetail = {
  id: 4, status: "submitted", source: "public", space_name: "Harbour Works", proposed_slug: "harbour", location: "Kochi",
  expected_members: 120, applicant_name: "Mira", applicant_email: "mira@example.com", applicant_phone: "", space_website_url: "",
  description: "A waterfront workshop.", organization_choice: "own", new_organization_name: "Harbour Collective", inviter_summary: "",
  created_at: "2026-11-01T00:00:00Z", verified_at: "2026-11-01T01:00:00Z", decided_at: null, changes_note: "", created_makerspace: null,
  revisions: [{ kind: "resubmitted", note: "Added the location.", changed_fields: ["location"], created_at: "2026-11-02T00:00:00Z" }],
};

function setup(list: () => unknown = () => ({ count: 1, next: null, previous: null, results: [REQUEST] })) {
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST" && path.endsWith("/approve")) return { request: { ...REQUEST, status: "accepted" }, makerspace: { id: 9, name: "Harbour Works", slug: "harbour" }, invitation: "sent" };
    if (init?.method === "POST") return { ...REQUEST, status: "changes_requested" };
    if (path === "/admin/platform/hosting-requests/4") return REQUEST;
    if (path.startsWith("/admin/organizations/")) return { count: 1, next: null, previous: null, results: [{ id: 3, name: "Kerala Makers" }] };
    return list();
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><OnboardingSection /></QueryClientProvider>);
}

async function openDrawer() {
  fireEvent.click(await screen.findByRole("button", { name: /Harbour Works/ }));
  return screen.findByRole("dialog", { name: "Harbour Works" });
}

function post(path: string) {
  const call = staffRequest.mock.calls.find(row => row[0] === path && (row[1] as RequestInit | undefined)?.method === "POST");
  return call ? JSON.parse((call[1] as RequestInit).body as string) : undefined;
}

beforeEach(() => { staffRequest.mockReset(); });

describe("OnboardingSection", () => {
  it("lists submitted requests and opens one with its history", async () => {
    setup();
    const drawer = await openDrawer();
    expect(within(drawer).getByText("120")).toBeInTheDocument();
    expect(within(drawer).getByText("Added the location.")).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/platform/hosting-requests?status=submitted&page=1", {}, "platform");
  });

  it("approves with a new owner organization and the invitation on by default", async () => {
    setup();
    const drawer = await openDrawer();
    fireEvent.click(within(drawer).getByRole("button", { name: "Approve…" }));
    const dialog = await screen.findByRole("dialog", { name: "Approve and create the space" });
    expect(within(dialog).getByRole("checkbox", { name: /Space Manager invitation/ })).toBeChecked();
    fireEvent.click(within(dialog).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(post("/admin/platform/hosting-requests/4/approve")).toEqual({
      name: "Harbour Works", slug: "harbour", invite_manager: true, new_organization_name: "Harbour Collective" }));
  });

  it("approves into an existing organization", async () => {
    setup();
    const drawer = await openDrawer();
    fireEvent.click(within(drawer).getByRole("button", { name: "Approve…" }));
    const dialog = await screen.findByRole("dialog", { name: "Approve and create the space" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "An existing organization" }));
    fireEvent.click(within(dialog).getByRole("checkbox", { name: /Space Manager invitation/ }));
    const select = await within(dialog).findByRole("combobox", { name: "Existing organization" });
    await within(select).findByRole("option", { name: "Kerala Makers" });
    fireEvent.change(select, { target: { value: "3" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(post("/admin/platform/hosting-requests/4/approve")).toEqual({
      name: "Harbour Works", slug: "harbour", invite_manager: false, organization_id: 3 }));
  });

  it.each([
    ["Request changes…", "request-changes", "note"],
    ["Reject…", "reject", "reason"],
  ])("%s sends a %s with the written %s", async (button, action, field) => {
    setup();
    const drawer = await openDrawer();
    fireEvent.click(within(drawer).getByRole("button", { name: button }));
    const dialog = await screen.findByRole("dialog", { name: action === "reject" ? "Reject this request" : "Request changes" });
    const submit = within(dialog).getAllByRole("button").find(row => row.getAttribute("type") === "submit")!;
    expect(submit).toBeDisabled();
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "Please add your opening hours." } });
    fireEvent.click(submit);
    await waitFor(() => expect(post(`/admin/platform/hosting-requests/4/${action}`)).toEqual({ [field]: "Please add your opening hours." }));
  });

  it("collapses to one line on a self-hosted deployment", async () => {
    setup(() => { throw new StructuredApiError(404, { detail: "Not found." }); });
    expect(await screen.findByText(SELF_HOST_NOTE)).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Status" })).not.toBeInTheDocument();
  });
});
