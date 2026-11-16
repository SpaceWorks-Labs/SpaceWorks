import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DonationSettingsForm } from "./DonationSettingsForm";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({
  ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"), staffRequest,
}));

const stored = { page_intro: "", suggested_amounts: ["500"], minimum_amount: "10.00", tax_exempt_registration_number: "",
  tax_exempt_valid_from: null, tax_exempt_valid_until: null, tax_exempt_registrant_pan: "", tax_exempt_note: "",
  is_nonprofit: false, legal_name: "", organization_registration_number: "", tax_exemptions: [], signatory_name: "",
  signatory_title: "", receipt_footer: "" };

function show(props: { taxOn?: boolean; canEdit?: boolean } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>
    <DonationSettingsForm makerspaceId={2} taxOn={props.taxOn ?? true} canEdit={props.canEdit ?? true} /></QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation((_path: string, init?: RequestInit) =>
    Promise.resolve(init?.method === "PUT" ? JSON.parse(String(init.body)) : stored));
});

describe("DonationSettingsForm: the non-profit profile (decision 242 m)", () => {
  it("explains what a space that is not a non-profit gets", async () => {
    show();
    const box = await screen.findByRole("checkbox", { name: "This makerspace is a non-profit" });
    expect(box).not.toBeChecked();
    expect(screen.getByText(/every receipt says it is not a tax receipt/)).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /Legal name/ })).not.toBeInTheDocument();
  });

  it("saves the profile with a typed tax-exemption registration", async () => {
    show();
    fireEvent.click(await screen.findByRole("checkbox", { name: "This makerspace is a non-profit" }));
    fireEvent.change(screen.getByRole("textbox", { name: /Legal name/ }), { target: { value: "Makers Trust" } });
    fireEvent.click(screen.getByRole("button", { name: "Add a registration" }));
    const registration = within(screen.getByRole("group", { name: "Registration 1" }));
    fireEvent.change(registration.getByRole("combobox", { name: "Scheme" }), { target: { value: "us_501c3" } });
    fireEvent.change(registration.getByRole("textbox", { name: "Registration number" }), { target: { value: "12-3456789" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Receipt signed by" }), { target: { value: "R. Treasurer" } });
    expect(screen.queryByRole("textbox", { name: /Institution's PAN/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/2/donations/settings",
      expect.objectContaining({ method: "PUT" })));
    const [, init] = staffRequest.mock.calls.find(([, call]) => call?.method === "PUT")!;
    expect(JSON.parse(init.body)).toMatchObject({ is_nonprofit: true, legal_name: "Makers Trust", signatory_name: "R. Treasurer",
      tax_exemptions: [{ scheme: "us_501c3", number: "12-3456789", valid_from: "", valid_until: "" }] });
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("asks for the institution's PAN only for an India 80G registration", async () => {
    show();
    fireEvent.click(await screen.findByRole("checkbox", { name: "This makerspace is a non-profit" }));
    fireEvent.click(screen.getByRole("button", { name: "Add a registration" }));
    expect(screen.getByRole("textbox", { name: /Institution's PAN/ })).toBeInTheDocument();
  });

  it("is read-only for anyone but the Space Manager", async () => {
    show({ canEdit: false });
    const box = await screen.findByRole("checkbox", { name: "This makerspace is a non-profit" });
    expect(box).toBeDisabled();
    expect(screen.getByText("Only the Space Manager changes these settings.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save settings" })).not.toBeInTheDocument();
  });
});
