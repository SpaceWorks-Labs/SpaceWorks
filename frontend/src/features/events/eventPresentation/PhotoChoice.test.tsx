import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import fixture from "../../../../../backend/tests/events/programme/contracts/fixtures/selected-photo-v3.json";
import { PhotoChoice } from "./PhotoChoice";
import { LiveTicketState } from "./LiveTicketState";

const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...await original<typeof import("../../../lib/api")>(), memberRequest: mocks.request }));

beforeEach(() => {
  mocks.request.mockReset();
  mocks.request.mockImplementation((path: string, options?: RequestInit) => {
    if (options?.method === "PATCH") return Promise.resolve({ ...fixture.no_photo, version: 1 });
    if (path.includes("profile-photo-options")) return Promise.resolve(fixture.options);
    return Promise.resolve({ ...fixture.defaults, id: null, version: 0 });
  });
});

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><PhotoChoice makerspaceId={1} eventId={42} eventName="Workshop" /></QueryClientProvider>);
  const details = view.container.querySelector("details")!; details.open = true; fireEvent(details, new Event("toggle"));
  return view;
}

describe("explicit selected-profile consent", () => {
  it("does not select the sole available membership or opt in to any consent", async () => {
    show();
    await screen.findByRole("option", { name: /Source Workshop/ });
    expect(screen.getByLabelText("Profile source")).toHaveValue("");
    for (const checkbox of screen.getAllByRole("checkbox")) expect(checkbox).not.toBeChecked();
  });
  it("shows both source and destination, and keeps print and public permissions separate", async () => {
    show(); await screen.findByRole("option", { name: /Source Workshop/ });
    fireEvent.change(screen.getByLabelText("Profile source"), { target: { value: "31" } });
    expect(screen.getByText(/Source: Source Workshop. Destination: Workshop/)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/printed badge/));
    fireEvent.click(screen.getByRole("button", { name: "Save photo choices" }));
    await waitFor(() => expect(mocks.request).toHaveBeenCalledWith(expect.stringContaining("presentation/"), expect.objectContaining({ method: "PATCH" })));
    const call = mocks.request.mock.calls.find((row) => row[1]?.method === "PATCH")!;
    expect(JSON.parse(call[1].body)).toMatchObject({ profile_id: 31, membership_id: 11,
      print_photo_consent: true, public_card_consent: false, public_card_scopes: [] });
  });
  it("clearing the profile clears print and public consent before submitting", async () => {
    show(); await screen.findByRole("option", { name: /Source Workshop/ });
    fireEvent.change(screen.getByLabelText("Profile source"), { target: { value: "31" } });
    fireEvent.click(screen.getByLabelText(/printed badge/));
    fireEvent.change(screen.getByLabelText("Profile source"), { target: { value: "" } });
    expect(screen.getByLabelText(/printed badge/)).not.toBeChecked();
    expect(screen.getByLabelText(/printed badge/)).toBeDisabled();
  });
});

it("ticket tear follows persisted attendance, including undo and reload state", () => {
  const view = render(<LiveTicketState status="registered" />);
  expect(screen.getByRole("status")).toHaveAttribute("data-ticket-state", "intact");
  view.rerender(<LiveTicketState status="attended" attendedAt="2026-10-18T10:00:00Z" />);
  expect(screen.getByRole("status")).toHaveAttribute("data-ticket-state", "torn");
  expect(screen.getByText("Checked in")).toBeInTheDocument();
  view.rerender(<LiveTicketState status="registered" />);
  expect(screen.getByRole("status")).toHaveAttribute("data-ticket-state", "intact");
});
