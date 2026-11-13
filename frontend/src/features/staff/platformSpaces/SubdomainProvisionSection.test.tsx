import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { SubdomainProvisionSection } from "./SubdomainProvisionSection";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const space = { id: 4, frontend_domain: null as string | null, frontend_domain_status: undefined, platform_hosting: true, is_platform_subdomain: false };

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}><SubdomainProvisionSection makerspaceId={4} /></QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); });

describe("SubdomainProvisionSection (0.12.0 row 24)", () => {
  it("provisions a platform subdomain for the space", async () => {
    staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/admin/makerspaces/4") return space;
      if (path === "/admin/makerspace/4/provision-subdomain" && init?.method === "POST") {
        return { ...space, frontend_domain: "alpha.spaceworks.test", is_platform_subdomain: true };
      }
      throw new Error(`unexpected ${path}`);
    });
    mount();
    expect(await screen.findByText("None — the space uses its /m/ path")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Subdomain label"), { target: { value: " alpha " } });
    fireEvent.click(screen.getByRole("button", { name: "Provision subdomain" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/4/provision-subdomain",
      { method: "POST", body: JSON.stringify({ label: "alpha" }) }, "platform"));
    expect(await screen.findByText("alpha.spaceworks.test (platform subdomain)")).toBeInTheDocument();
  });

  it("warns that a custom domain will be replaced and shows the server's refusal", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/admin/makerspaces/4") return { ...space, frontend_domain: "lab.example.org" };
      throw new StructuredApiError(400, { label: ["This subdomain label is reserved."] });
    });
    mount();
    expect(await screen.findByText("This replaces the custom domain lab.example.org.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Subdomain label"), { target: { value: "admin" } });
    fireEvent.click(screen.getByRole("button", { name: "Provision subdomain" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("is not offered on a self-hosted deployment", async () => {
    staffRequest.mockResolvedValue({ ...space, platform_hosting: false });
    const { container } = mount();
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
