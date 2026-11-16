import type React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { JoinPage } from "../organizations/idProgrammes/JoinPage";
import { ApprovalLevelSelect } from "./ApprovalLevelSelect";
import { CardVerifyPage, checkedLine, initials } from "./CardVerifyPage";
import { StaffPhotoDialog } from "./StaffPhotoDialog";

const api = vi.hoisted(() => ({ publicV1Request: vi.fn(), memberRequest: vi.fn(), memberRequestBlob: vi.fn(), staffRequest: vi.fn(),
  getAccessToken: vi.fn(() => "token"), refreshAccessToken: vi.fn(() => Promise.resolve()) }));
vi.mock("../../lib/api", async () => ({ ...(await vi.importActual<typeof import("../../lib/api")>("../../lib/api")), ...api }));

function renderAt(path: string, pattern: string, element: React.JSX.Element) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>
    <Routes><Route path={pattern} element={element} /></Routes></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { Object.values(api).forEach((mock) => "mockReset" in mock && mock.mockReset()); });

const valid = { status: "valid", valid: true, issuer: { kind: "organisation", name: "Makers Guild", logo_url: null },
  label: "Student ID", number: "MKG-2026-0001", valid_until: "2027-06-30", holder: { name: "Priya Raman", photo_url: null },
  note: "", checked_at: "2026-11-03T10:00:00Z", timezone: "Asia/Kolkata" };

describe("card check page (SPEC §7)", () => {
  it("shows the valid band, caps labels, initials and the issuer footnote with its time zone", async () => {
    api.publicV1Request.mockResolvedValue(valid);
    renderAt("/verify/c/tok", "/verify/c/:token", <CardVerifyPage />);
    expect(await screen.findByRole("heading", { name: "Valid card" })).toBeVisible();
    expect(screen.getByText("This card is genuine and in date.")).toBeVisible();
    expect(screen.getByText("Programme")).toBeVisible();
    expect(screen.getByText("MKG-2026-0001")).toBeVisible();
    expect(screen.getByText("PR")).toBeInTheDocument();
    expect(screen.getByText(/checks this card against Makers Guild's records/)).toHaveTextContent("(Asia/Kolkata)");
    expect(document.head.querySelector('meta[name="referrer"]')?.getAttribute("content")).toBe("no-referrer");
  });

  it("says an expired card is no longer in date", async () => {
    api.publicV1Request.mockResolvedValue({ ...valid, status: "expired", valid: false, holder: null });
    renderAt("/verify/c/tok", "/verify/c/:token", <CardVerifyPage />);
    expect(await screen.findByRole("heading", { name: "Expired card" })).toBeVisible();
    expect(screen.getByText("This card was genuine but is no longer in date.")).toBeVisible();
  });

  it("answers too many checks plainly", async () => {
    api.publicV1Request.mockRejectedValue(new StructuredApiError(429, { detail: "Slow down." }));
    renderAt("/verify/c/tok", "/verify/c/:token", <CardVerifyPage />);
    expect(await screen.findByText("Too many checks. Try again in a minute.")).toBeVisible();
  });

  it("formats initials and the checked line", () => {
    expect(initials("alexandra montgomery fitzgerald")).toBe("AM");
    expect(checkedLine({ checked_at: "2026-11-03T10:00:00Z", timezone: "Not/AZone" })).toContain("(Not/AZone)");
  });
});

describe("ApprovalLevelSelect (#136)", () => {
  it("offers inherit with what it means now, on and off", () => {
    const onChange = vi.fn();
    render(<ApprovalLevelSelect label="Design changes for this event" value={null} inherited={false}
      inheritLabel="Follow the organisation and space" onChange={onChange} />);
    const select = screen.getByLabelText("Design changes for this event");
    expect(screen.getByRole("option", { name: "Follow the organisation and space (now: no approval)" })).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "on" } });
    expect(onChange).toHaveBeenLastCalledWith(true);
    fireEvent.change(select, { target: { value: "inherit" } });
    expect(onChange).toHaveBeenLastCalledWith(null);
  });
});

describe("StaffPhotoDialog (X25)", () => {
  it("keeps the photo controls off until staff confirm the holder agreed", () => {
    // The dialog also hosts the background-eraser panel (D314c), which reads through TanStack Query.
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><StaffPhotoDialog holderName="Asha" photoPath="/admin/member-cards/4/photo" onClose={vi.fn()} onSaved={vi.fn()} /></QueryClientProvider>);
    expect(screen.getByLabelText("Choose a photo")).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: /Asha agreed to this photo/ }));
    expect(screen.getByLabelText("Choose a photo")).toBeEnabled();
  });
});

describe("JoinPage Saved-details prefill (P24)", () => {
  const programme = { name: "Student ID", slug: "student-id", description: "", organization_name: "Makers Guild",
    photo_mode: "none", requires_approval: true, registration_open: true, state: "open",
    questions: [{ key: "college", label: "College", type: "text", required: true, prefill: true },
      { key: "note", label: "Note", type: "text", required: false, prefill: false }] };

  it("reads Saved details only when asked and fills only empty answers", async () => {
    api.publicV1Request.mockResolvedValue(programme);
    api.memberRequest.mockResolvedValue({ values: { college: "College of Engineering" } });
    renderAt("/o/guild/ids/student-id", "/o/:organizationSlug/ids/:programmeSlug", <JoinPage />);
    const button = await screen.findByRole("button", { name: "Fill from my Saved details" });
    expect(api.memberRequest).not.toHaveBeenCalled();
    fireEvent.click(button);
    await waitFor(() => expect(screen.getByLabelText("College")).toHaveValue("College of Engineering"));
    expect(api.memberRequest).toHaveBeenCalledWith("/public/organizations/guild/id-programmes/student-id/prefill");
    expect(screen.getByText(/Filled 1 answer/)).toBeVisible();
  });

  it("hides the button when no question can be prefilled", async () => {
    api.publicV1Request.mockResolvedValue({ ...programme, questions: [programme.questions[1]] });
    renderAt("/o/guild/ids/student-id", "/o/:organizationSlug/ids/:programmeSlug", <JoinPage />);
    expect(await screen.findByLabelText(/Note/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Fill from my Saved details" })).not.toBeInTheDocument();
  });
});
