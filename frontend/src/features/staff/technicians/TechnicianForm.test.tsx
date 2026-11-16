import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TechnicianForm } from "./TechnicianForm";
import type { Technician } from "./techniciansApi";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest: request }));

const tech = (over: Partial<Technician> = {}): Technician => ({
  id: 4, kind: "external", person_id: null, name: "Ravi Repairs", email: "ravi@x.test", phone: "+91 90000", telegram_handle: "@ravi",
  channels: ["email", "telegram"], notes: "Weekdays", is_archived: false, coverage: [{ kind: "inventory", id: null }],
  consent: { email: true, telegram: true, whatsapp: false, sms: false }, opt_in_pending: false, ...over,
});

let writes: Array<{ path: string; method: string; body?: Record<string, unknown> }>;
let failWith: Error | undefined;

function mount(props: Partial<Parameters<typeof TechnicianForm>[0]> = {}) {
  const onClose = vi.fn();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <TechnicianForm makerspaceId={3} technician={null} canSetCoverage onClose={onClose} {...props} /></QueryClientProvider>);
  return { onClose };
}
beforeEach(() => {
  writes = []; failWith = undefined;
  request.mockReset();
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method !== "GET") {
      writes.push({ path, method, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (failWith) throw failWith;
      if (path.endsWith("/opt-in-link")) return { url: "https://app.test/opt/abc", telegram_start: "/start abc", expires_at: "2026-12-01", emailed: true };
      return {};
    }
    if (path.endsWith("/candidates")) return [{ person_id: 11, name: "Asha Staff", is_technician: false }, { person_id: 12, name: "Bo Tech", is_technician: true }];
    if (path.endsWith("/machine-types")) return [{ id: 21, name: "Laser" }, { id: 22, name: "Printer" }];
    if (path.includes("/spaces/")) return { results: [{ id: 31, name: "Wet lab" }] };
    return [];
  });
});

describe("adding an outside contractor", () => {
  it("requires a name, then posts the form with email forced into the channels and chosen coverage", async () => {
    const { onClose } = mount();
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "  New Co  " } });
    expect(save).toBeEnabled();
    fireEvent.change(screen.getByRole("textbox", { name: "Email" }), { target: { value: "n@x.test" } });
    fireEvent.change(screen.getByLabelText("Phone (for WhatsApp or SMS)"), { target: { value: "123" } });
    fireEvent.change(screen.getByLabelText("Telegram handle (optional)"), { target: { value: "@n" } });
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "n" } });
    fireEvent.click(screen.getByLabelText("WhatsApp"));
    fireEvent.click(await screen.findByLabelText("Laser"));
    fireEvent.click(await screen.findByLabelText("Wet lab"));
    fireEvent.click(screen.getByLabelText("All inventory items"));
    fireEvent.click(save);
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(writes[0]).toMatchObject({ path: "/admin/makerspaces/3/technicians", method: "POST" });
    expect(writes[0].body).toMatchObject({ name: "  New Co  ", email: "n@x.test", phone: "123", telegram_handle: "@n", notes: "n", channels: ["email", "whatsapp"],
      coverage: [{ kind: "machine_type", id: 21 }, { kind: "room", id: 31 }, { kind: "inventory", id: null }] });
    expect(writes[0].body).not.toHaveProperty("person_id");
  });
  it("keeps email checked and disabled, and toggles another channel off again", () => {
    mount();
    const email = screen.getByLabelText("Email", { selector: "input[type=checkbox]" });
    expect(email).toBeChecked();
    expect(email).toBeDisabled();
    const sms = screen.getByLabelText("SMS");
    fireEvent.click(sms);
    expect(sms).toBeChecked();
    fireEvent.click(sms);
    expect(sms).not.toBeChecked();
  });
  it("toggling a coverage row twice removes it", async () => {
    mount();
    const laser = await screen.findByLabelText("Laser");
    fireEvent.click(laser);
    expect(laser).toBeChecked();
    fireEvent.click(laser);
    expect(laser).not.toBeChecked();
  });
  it("shows the save failure in an alert and stays open", async () => {
    failWith = new Error("Name already taken");
    const { onClose } = mount();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Dup" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Name already taken");
    expect(onClose).not.toHaveBeenCalled();
  });
  it("cancel closes without saving", () => {
    const { onClose } = mount();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
    expect(writes).toHaveLength(0);
  });
  it("ignores a submit while the name is blank", () => {
    mount();
    fireEvent.submit(screen.getByLabelText("Name").closest("form")!);
    expect(writes).toHaveLength(0);
  });
});

describe("adding someone on staff", () => {
  it("lists candidates, marks existing technicians, needs a person, and posts person_id", async () => {
    const { onClose } = mount();
    fireEvent.click(screen.getByLabelText("Someone on staff"));
    expect(screen.queryByLabelText("Name")).toBeNull();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(await screen.findByRole("option", { name: "Bo Tech (Technician)" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Person"), { target: { value: "11" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(writes[0].body).toMatchObject({ person_id: 11 });
    expect(writes[0].body).toHaveProperty("coverage");
  });
  it("hides coverage for an in-house technician without the coverage permission", async () => {
    mount({ canSetCoverage: false });
    fireEvent.click(screen.getByLabelText("Someone on staff"));
    expect(screen.getByText("Only the Space Manager sets what an in-house technician covers.")).toBeInTheDocument();
    expect(screen.queryByText("Covers")).toBeNull();
    await screen.findByRole("option", { name: "Asha Staff" });
    fireEvent.change(screen.getByLabelText("Person"), { target: { value: "11" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].body).not.toHaveProperty("coverage");
  });
  it("lets a contractor's coverage be edited even without the coverage permission", async () => {
    mount({ canSetCoverage: false });
    expect(await screen.findByLabelText("Laser")).toBeEnabled();
  });
});

describe("editing an existing technician", () => {
  it("loads their values, hides the who-picker, marks channels needing opt-in and patches by id", async () => {
    const { onClose } = mount({ technician: tech() });
    expect(screen.getByRole("heading", { name: "Ravi Repairs" })).toBeInTheDocument();
    expect(screen.queryByText("Who")).toBeNull();
    expect(screen.getByLabelText("Name")).toHaveValue("Ravi Repairs");
    expect(screen.getByLabelText("All inventory items")).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /^WhatsApp/ })).not.toBeChecked();
    expect(screen.getByText(/WhatsApp \(needs opt-in\)/)).toBeInTheDocument();
    expect(screen.queryByText(/Telegram \(needs opt-in\)/)).toBeNull();
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "Weekends too" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(writes[0]).toMatchObject({ path: "/admin/technicians/4", method: "PATCH" });
    expect(writes[0].body).toMatchObject({ notes: "Weekends too", channels: ["email", "telegram"] });
  });
  it("an in-house technician's coverage is read-only text without the permission, and the PATCH omits it", async () => {
    mount({ technician: tech({ kind: "in_house", person_id: 11 }), canSetCoverage: false });
    expect(screen.getByText("Only the Space Manager sets what an in-house technician covers.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].body).not.toHaveProperty("coverage");
  });
});

describe("technician extras", () => {
  it("sends an opt-in link and shows the link, the Telegram start text and the emailed note", async () => {
    mount({ technician: tech() });
    fireEvent.click(screen.getByRole("button", { name: "Send chat opt-in link" }));
    expect(await screen.findByText(/Emailed\./)).toBeInTheDocument();
    expect(screen.getByText("https://app.test/opt/abc")).toBeInTheDocument();
    expect(screen.getByText("/start abc")).toBeInTheDocument();
    expect(writes[0]).toMatchObject({ path: "/admin/technicians/4/opt-in-link", method: "POST" });
  });
  it("withdraws consent only for channels they consented to", async () => {
    mount({ technician: tech({ consent: { email: true, telegram: true, whatsapp: false, sms: true } }) });
    expect(screen.getByRole("button", { name: "Stop Telegram" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop SMS" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop WhatsApp" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Stop SMS" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({ path: "/admin/technicians/4/consent", method: "POST", body: { channel: "sms" } });
  });
  it("archives and closes, but offers no archive for an already archived technician", async () => {
    const { onClose } = mount({ technician: tech() });
    fireEvent.click(screen.getByRole("button", { name: "Archive" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(writes[0]).toMatchObject({ path: "/admin/technicians/4", method: "DELETE" });
  });
  it("hides Archive when already archived", () => {
    mount({ technician: tech({ is_archived: true }) });
    expect(screen.queryByRole("button", { name: "Archive" })).toBeNull();
  });
  it("shows an extras failure in an alert", async () => {
    failWith = new Error("Opt-in blocked");
    mount({ technician: tech() });
    fireEvent.click(screen.getByRole("button", { name: "Send chat opt-in link" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Opt-in blocked");
  });
});
