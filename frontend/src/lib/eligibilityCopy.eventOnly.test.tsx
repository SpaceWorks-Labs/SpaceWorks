import { expect, it } from "vitest";

import { StructuredApiError } from "./api/errors";
import { eligibilityMessage } from "./eligibilityCopy";

it("names the event-only items a request, self-checkout or handout refused", () => {
  const error = new StructuredApiError(409, { code: "event_only_product", detail: "x", products: ["Oscilloscope", "VR headset"] });
  expect(eligibilityMessage(error)).toBe("These items are lent only through an event: Oscilloscope, VR headset. Remove them, or ask the event organizers to request them for you.");
  expect(eligibilityMessage(new StructuredApiError(409, { code: "event_only_product" }))).toMatch(/lent only through an event/);
});

it("explains renewal refusals", () => {
  expect(eligibilityMessage(new StructuredApiError(400, { code: ["self_renewal_off"] }))).toMatch(/Ask space staff to renew it/);
  expect(eligibilityMessage(new StructuredApiError(400, { code: "renewals_off" }))).toMatch(/switched off/);
});
