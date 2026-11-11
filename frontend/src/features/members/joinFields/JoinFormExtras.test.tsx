import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { memberRequest } from "../../../lib/api";
import { AdmissionJoin } from "../AdmissionJoin";
import type { PublicAdmission } from "../membershipAdmissionApi";
import { e164, validateExtras, EMPTY_EXTRAS } from "./joinFieldsModel";

vi.mock("../../../lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), memberRequest: vi.fn() }));

const settings: PublicAdmission = {
  join_mode: "approval", vouches_required: 1, payment_timing: "after_activation", application_schema: null,
  default_plan: { id: 3, name: "Annual", amount: "0.00", currency: "inr" }, joining_fee: "0.00",
  join_fields: { photo: "required", phone: "optional", state: "required" },
};

beforeEach(() => { vi.mocked(memberRequest).mockReset(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe("join form extras (parity O-B2)", () => {
  it("builds the full number from the country code and refuses a malformed one", () => {
    expect(e164({ ...EMPTY_EXTRAS, national: "098765 43210" })).toBe("+919876543210");
    expect(e164({ ...EMPTY_EXTRAS, region: "GB", national: "7700 900123" })).toBe("+447700900123");
    const modes = { photo: "off", phone: "required", state: "hidden" } as const;
    expect(validateExtras(modes, { ...EMPTY_EXTRAS, national: "12" })).toHaveProperty("phone");
    expect(validateExtras(modes, EMPTY_EXTRAS)).toHaveProperty("phone");
    expect(validateExtras(modes, EMPTY_EXTRAS, { phone: true })).toEqual({});
  });

  it("asks only for what the plan wants and blocks a required photo and state", () => {
    const join = vi.fn();
    render(<AdmissionJoin settings={settings} makerspaceId={7} signedIn pending={false} onJoin={join} onSignIn={vi.fn()} />);
    expect(screen.getByLabelText(/Phone number \(optional\)/)).toBeVisible();
    expect(screen.getByLabelText(/State \(required\)/)).toBeVisible();
    expect(screen.getByText("Your photo (required)")).toBeVisible();
    fireEvent.submit(screen.getByRole("button", { name: "Request to join" }).closest("form")!);
    expect(join).not.toHaveBeenCalled();
    expect(screen.getByText("Choose your state.")).toBeVisible();
    expect(screen.getByText("Add a photo of yourself.")).toBeVisible();
  });

  it("hides every extra when the plan asks for none", () => {
    render(<AdmissionJoin settings={{ ...settings, join_fields: { photo: "off", phone: "hidden", state: "hidden" } }} makerspaceId={7} signedIn pending={false} onJoin={vi.fn()} onSignIn={vi.fn()} />);
    expect(screen.queryByLabelText(/Phone number/)).toBeNull();
    expect(screen.queryByText(/Your photo/)).toBeNull();
  });

  it("uploads a consented photo to staging, then sends its key with the phone and state", async () => {
    vi.mocked(memberRequest).mockResolvedValue({ object_key: "member-cards/7/abc.jpg", content_type: "image/jpeg", url: "https://storage.test/put", method: "PUT", headers: {} });
    const upload = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal("fetch", upload);
    const join = vi.fn();
    render(<AdmissionJoin settings={settings} makerspaceId={7} signedIn pending={false} onJoin={join} onSignIn={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Phone number/), { target: { value: "98765 43210" } });
    fireEvent.change(screen.getByLabelText(/State \(required\)/), { target: { value: "32" } });
    const photo = new File(["x"], "me.jpg", { type: "image/jpeg" });
    fireEvent.change(screen.getByLabelText("Choose a photo"), { target: { files: [photo] } });
    fireEvent.submit(screen.getByRole("button", { name: "Request to join" }).closest("form")!);
    expect(await screen.findByText("Tick the consent box to send your photo.")).toBeVisible();
    expect(memberRequest).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("checkbox", { name: /I agree to my photo being stored privately/ }));
    fireEvent.submit(screen.getByRole("button", { name: "Request to join" }).closest("form")!);
    await waitFor(() => expect(join).toHaveBeenCalledWith({}, { join_fields: {
      phone: "+919876543210", state_code: "32", photo: { object_key: "member-cards/7/abc.jpg", content_type: "image/jpeg", consent: true } } }));
    expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/7/admission/photo", { method: "POST", body: JSON.stringify({ content_type: "image/jpeg", plan_id: 3 }) });
    expect(upload).toHaveBeenCalledWith("https://storage.test/put", expect.objectContaining({ method: "PUT", body: photo }));
  });
});
