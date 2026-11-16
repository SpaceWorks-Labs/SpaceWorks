import { expect, it } from "vitest";
import { parseContext } from "./api";
const common = { active: true, generation: "11111111-1111-4111-8111-111111111111", revision: 1, can_write: false, event_id: 4 };
it("distinguishes an omitted participant from known absence", () => {
  const hidden = parseContext({ ...common, may_view_participant: false }, "event");
  expect("participant_registration_id" in hidden).toBe(false);
  expect(() => parseContext({ ...common, may_view_participant: false, participant_registration_id: null }, "event")).toThrow();
  expect(parseContext({ ...common, may_view_participant: true, participant_registration_id: null }, "event").participant_registration_id).toBeNull();
});
it("rejects unsafe revisions, identifiers and invalid generations", () => {
  for (const change of [{ revision: Number.MAX_SAFE_INTEGER + 1 }, { event_id: 0 }, { revision: -1 }, { generation: "invalid" }]) {
    expect(() => parseContext({ ...common, may_view_participant: true, participant_registration_id: null, ...change }, "event")).toThrow();
  }
});

it("rejects an event write grant when participant visibility is withheld", () => {
  expect(() => parseContext({ ...common, can_write: true, may_view_participant: false }, "event")).toThrow();
});
