import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { publicV1Request } from "../../lib/api";
import { EMPTY_HOSTING_FORM, hostingRequestBody } from "./hostingForm";
import { HostingRequestPage } from "./HostingRequestPage";

vi.mock("../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../lib/api")>(), publicV1Request: vi.fn() }));

function show(config: unknown) {
  vi.mocked(publicV1Request).mockImplementation(async (path: string) => path === "/config" ? config : { detail: "ok" });
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><HostingRequestPage /></MemoryRouter></QueryClientProvider>);
}

function fill(label: RegExp | string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

beforeEach(() => vi.mocked(publicV1Request).mockReset());

describe("hosting request kinds (decision 295)", () => {
  it("offers no kind choice when the deployment takes makerspace requests only", async () => {
    show({ hosting_requests: { enabled: true } });
    expect(await screen.findByLabelText("Makerspace name")).toBeVisible();
    expect(screen.queryByRole("group", { name: "What do you want to set up?" })).not.toBeInTheDocument();
    expect(screen.getByLabelText(/^Location/)).toBeRequired();
  });

  it("relabels the form for an organization and sends requested_kind without a location", async () => {
    show({ hosting_requests: { enabled: true, kinds: ["makerspace", "organization"] } });
    fireEvent.click(await screen.findByRole("radio", { name: /An organization/ }));
    expect(screen.getByLabelText("Organization name")).toBeVisible();
    expect(screen.getByLabelText(/Where you meet/)).not.toBeRequired();
    expect(screen.queryByLabelText(/Organization name \(optional\)/)).not.toBeInTheDocument();
    fill("Your name", "Asha"); fill("Email", "asha@example.com"); fill("Organization name", "Chess Society");
    fill(/About your organization/, "A city chess society that runs weekly club nights.");
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/public/hosting/requests", expect.anything()));
    const call = vi.mocked(publicV1Request).mock.calls.find(([path]) => path === "/public/hosting/requests")!;
    const body = JSON.parse(String(call[1]?.body));
    expect(body).toMatchObject({ requested_kind: "organization", space_name: "Chess Society" });
    expect(body).not.toHaveProperty("location");
  });

  it("keeps a makerspace body unchanged", () => {
    const body = hostingRequestBody({ ...EMPTY_HOSTING_FORM, location: "Kochi" });
    expect(body).not.toHaveProperty("requested_kind");
    expect(body.location).toBe("Kochi");
  });
});
