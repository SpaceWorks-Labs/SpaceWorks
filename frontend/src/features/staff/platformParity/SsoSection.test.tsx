import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { SsoSection } from "./SsoSection";

vi.mock("../../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);

const provider = { id: 3, slug: "keycloak", display_name: "Keycloak", issuer: "https://id.example.org/realms/main",
  jwks_url: "https://id.example.org/certs", client_id: "spaceworks", is_enabled: true, allow_auto_link: false,
  created_at: "2026-10-01T10:00:00Z", updated_at: "2026-10-02T10:00:00Z" };

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><SsoSection /></QueryClientProvider>);
}

describe("SsoSection", () => {
  beforeEach(() => {
    request.mockReset();
    request.mockImplementation(async (_path, init) => (init?.method ? provider : { count: 1, next: null, previous: null, results: [provider] }) as never);
  });

  it("turns a provider off instead of deleting it", async () => {
    renderSection();
    expect(await screen.findByText("Keycloak")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Turn off Keycloak" }));
    fireEvent.click(screen.getByRole("button", { name: "Turn off" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/oidc-providers/3",
      { method: "PATCH", body: JSON.stringify({ is_enabled: false }) }, "platform"));
  });

  it("refuses an issuer that is not https", async () => {
    renderSection();
    fireEvent.click(screen.getByRole("button", { name: "New provider" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Issuer" }), { target: { value: "http://id.example.org" } });
    expect(screen.getByText("The issuer must start with https://.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add provider" })).toBeDisabled();
  });
});
