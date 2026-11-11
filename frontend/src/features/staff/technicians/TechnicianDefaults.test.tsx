import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TechnicianDefaults, type Area } from "./TechnicianDefaults";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest }));

const tech = { id: 5, kind: "in_house", person_id: 9, name: "Ravi", email: "", phone: "", telegram_handle: "", channels: ["email"],
  notes: "", is_archived: false, coverage: [{ kind: "machine_type", id: 2, label: "Laser cutters" }],
  consent: { email: true, telegram: false, whatsapp: false, sms: false }, opt_in_pending: false };
const saved = { id: 1, area: "machines", machine_type_id: 2, room_id: null, contact_id: 5 };

function show(areas: Area[]) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <TechnicianDefaults makerspaceId={4} areas={areas} /></QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); });

describe("TechnicianDefaults", () => {
  it("adds a default narrowed to a machine type the technician covers", async () => {
    staffRequest.mockImplementation((path: string, init?: RequestInit) => Promise.resolve(
      String(path).endsWith("/technicians") ? [tech] : init?.method === "POST" ? [saved] : []));
    show(["machines"]);
    expect(await screen.findByText("No defaults yet.")).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText("Technician"), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText("Only for"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Add default" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/technician-defaults", expect.objectContaining({
      method: "POST", body: JSON.stringify({ area: "machines", contact_id: 5, machine_type_id: 2, room_id: null }) })));
    expect(await screen.findByText("Ravi · Machines · Laser cutters")).toBeInTheDocument();
  });

  it("removes a default with remove=true, and offers no form without a managed area", async () => {
    staffRequest.mockImplementation((path: string, init?: RequestInit) => Promise.resolve(
      String(path).endsWith("/technicians") ? [tech] : init?.method === "POST" ? [] : [saved]));
    show([]);
    expect(await screen.findByText("Ravi · Machines · Laser cutters")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add default" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove" })).toBeNull();
  });

  it("lets an area manager remove its own default", async () => {
    staffRequest.mockImplementation((path: string, init?: RequestInit) => Promise.resolve(
      String(path).endsWith("/technicians") ? [tech] : init?.method === "POST" ? [] : [saved]));
    show(["machines"]);
    fireEvent.click(await screen.findByRole("button", { name: "Remove" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/technician-defaults?remove=true",
      expect.objectContaining({ method: "POST" })));
  });
});
