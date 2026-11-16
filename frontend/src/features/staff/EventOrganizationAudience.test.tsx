import { fireEvent, render as rtlRender, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// Screens now read query-backed switches (help-centre bootstrap, #184 charge flags), so every render needs a client.
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children?: Parameters<typeof rtlRender>[0] }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return rtlRender(ui, { wrapper, ...options });
}
import { describe, expect, it, vi } from "vitest";
import { EventOrganizationAudience } from "./EventOrganizationAudience";
import { EventFields, emptyEventForm } from "./EventFormFields";
// The price-list note reads the staff session cache; these forms are tested without one.
vi.mock("./pricing/PricingNote", () => ({ EventPriceNote: () => null }));

describe("organization audience configuration", () => {
  it("hides the new option when its feature is off", () => {
    render(<EventFields values={emptyEventForm} setValues={() => {}} />);
    expect(screen.queryByRole("option", { name: "Participating organizations" })).not.toBeInTheDocument();
  });
  it("offers the audience with its feature and preserves the selected enum", () => {
    const change = vi.fn();
    render(<EventFields values={emptyEventForm} setValues={change} organizationAudienceEnabled />);
    fireEvent.change(screen.getByLabelText(/Registration audience/), { target: { value: "participating_organizations" } });
    expect(change.mock.calls[0][0].registration_audience).toBe("participating_organizations");
  });
  it("explains live candidates and explicitly confirms imported policy", () => {
    const confirm = vi.fn();
    render(<EventOrganizationAudience event={{ registration_audience: "participating_organizations",
      participating_organizations: [{ id: 1, name: "A" }, { id: 2, name: "B" }, { id: 3, name: "C" }],
      organization_admission_blocked: true }} onReconfigure={confirm} />);
    expect(screen.getByText("A, B, C")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("blocked");
    expect(screen.queryByRole("textbox", { name: /organization/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm local audience" }));
    expect(confirm).toHaveBeenCalledOnce();
  });
  it("offers no review mutation to an actor lacking edit_details", () => {
    render(<EventOrganizationAudience event={{ registration_audience: "participating_organizations",
      participating_organizations: [], organization_admission_blocked: true }} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText("No usable participating organizations.")).toBeInTheDocument();
  });
});
