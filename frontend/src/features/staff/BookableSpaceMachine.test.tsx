import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BookableSpaceForm, valuesForSpace } from "./BookableSpaceForm";
import type { BookableSpace } from "./bookingsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest }));
vi.mock("../forms/CustomFormBuilder", () => ({ CustomFormBuilder: () => null }));

describe("machine time booking", () => {
  it("offers the Machine time kind with a machine picker and sends the machine", async () => {
    staffRequest.mockImplementation(async (path: string) => path.includes("/machines")
      ? { count: 1, next: null, results: [{ id: 4, name: "Laser A", is_active: true, machine_type: { id: 7, name: "Laser cutters" } }] }
      : { count: 0, next: null, previous: null, results: [] });
    const onSubmit = vi.fn();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(["staff", "makerspaces"], [{ id: 2, enabled_modules: ["machines"], enabled_features: ["machines.time_booking"] }]);
    render(<QueryClientProvider client={client}><BookableSpaceForm makerspaceId={2} onSubmit={onSubmit} pending={false} submitLabel="Create" /></QueryClientProvider>);
    fireEvent.change(screen.getByRole("textbox", { name: "Name" }), { target: { value: "Laser time" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Space type" }), { target: { value: "machine" } });
    expect(screen.queryByRole("combobox", { name: /Machine type for certification/ })).not.toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "Laser A · Laser cutters" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Machine" }), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ kind: "machine", machine: 4 })));
  });

  it("hides the kind when the switch is off and clears a link when the kind changes", async () => {
    staffRequest.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    const onSubmit = vi.fn();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(["staff", "makerspaces"], [{ id: 2, enabled_modules: ["machines"], enabled_features: [] }]);
    const space = { name: "Laser time", kind: "machine", machine: 4, machine_type: 7, description: "", capacity: 0, location: "", is_public: false,
      show_public_availability: false, show_public_booker_names: false, payment_amount: "0.00", custom_form: null, requester_notifications_enabled: null } as unknown as BookableSpace;
    render(<QueryClientProvider client={client}><BookableSpaceForm makerspaceId={2} initialValues={valuesForSpace(space)} onSubmit={onSubmit} pending={false} submitLabel="Save" /></QueryClientProvider>);
    expect(screen.getByRole("option", { name: "Machine time" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Space type" }), { target: { value: "bench" } });
    expect(screen.queryByRole("option", { name: "Machine time" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ kind: "bench", machine: null })));
  });
});
