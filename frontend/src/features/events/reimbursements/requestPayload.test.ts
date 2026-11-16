import { describe, expect, it } from "vitest";
import contract from "../../../../../backend/tests/events/programme/contracts/reimbursement_addon.json";
import { requestPayload, requestState } from "./requestPayload";
import type { RequestContext, RequestSubmission } from "./types";
const expected = contract.submission.ordinary.payload.reimbursement_request as RequestSubmission;
const context: RequestContext = { programme_id: expected.programme_id, programme_version: expected.programme_version,
  schema: contract.submission.fixed_request_schema as RequestContext["schema"], allowed_categories: ["rail", "lodging"], currency: "INR", min_distance_km: null };
describe("fixed travel support consent and mapping", () => {
  it("reconciles exactly to BOTH canonical frozen submission blocks", () => {
    const payload = requestPayload(context, requestState(expected), true, "550.000");
    expect(payload).toEqual(expected);
    expect(payload).toEqual(contract.submission.application.payload.reimbursement_request);
    expect(payload).not.toHaveProperty("answers");
    expect(payload).not.toHaveProperty("save_choices");
  });
  it("requires affirmative consent and a positive programme-currency estimate", () => {
    expect(() => requestPayload(context, requestState(expected), false, "")).toThrow(/choose/i);
    const state = requestState(expected); state.answers.estimate_rail = { amount_minor: 1.5, currency: "INR" };
    expect(() => requestPayload(context, state, true, "")).toThrow(/positive/i);
    state.answers.estimate_rail = { amount_minor: 1, currency: "USD" };
    expect(() => requestPayload(context, state, true, "")).toThrow(/currency/i);
  });
  it("refuses invalid self-reported distance without creating an estimate", () => {
    for (const distance of ["-1", "40076", "550.0001", "1e3"]) expect(() => requestPayload(context, requestState(expected), true, distance)).toThrow(/distance/i);
    expect(() => requestPayload({ ...context, min_distance_km: "10" }, requestState(expected), true, "")).toThrow();
  });
});
