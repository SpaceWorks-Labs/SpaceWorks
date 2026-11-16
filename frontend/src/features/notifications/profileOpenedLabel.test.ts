import { expect, it } from "vitest";
import { notificationEventLabel } from "./notificationEventLabels";

it("labels the one-time profile_opened notice", () => {
  expect(notificationEventLabel("profile_opened")).toBe("Profile opened");
});
