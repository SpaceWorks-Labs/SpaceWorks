import { describe, expect, it } from "vitest";
import { emptyWeek } from "../staff/makerspaceProfileForm";
import { summariseHours } from "./openingHours";

const weekly = { ...emptyWeek(), mon: [{ start: "09:00", end: "13:00" }, { start: "14:00", end: "18:00" }], sat: [{ start: "10:00", end: "16:00" }] };
// 2026-10-18T20:00Z is Sunday evening in London but already Monday 01:30 in Kolkata.
const instant = new Date("2026-10-18T20:00:00Z");

describe("summariseHours", () => {
  it("returns null when no weekly hours are published", () => {
    expect(summariseHours({}, "Asia/Kolkata", instant)).toBeNull();
    expect(summariseHours(undefined, "Asia/Kolkata", instant)).toBeNull();
    expect(summariseHours({ weekly: {}, exceptions: { "2026-10-19": [] } }, "Asia/Kolkata", instant)).toBeNull();
  });

  it("reads today in the makerspace's zone, not the visitor's", () => {
    const kolkata = summariseHours({ weekly, exceptions: {} }, "Asia/Kolkata", instant)!;
    expect(kolkata.today).toBe("Open today 09:00–13:00, 14:00–18:00");
    expect(kolkata.week.find((row) => row.isToday)?.day).toBe("Monday");
    expect(summariseHours({ weekly, exceptions: {} }, "Europe/London", instant)!.today).toBe("Closed today");
  });

  it("lets a dated exception override the weekly hours", () => {
    const closed = summariseHours({ weekly, exceptions: { "2026-10-19": [] } }, "Asia/Kolkata", instant)!;
    expect(closed.today).toBe("Closed today");
    const special = summariseHours({ weekly, exceptions: { "2026-10-19": [{ start: "12:00", end: "15:00" }] } }, "Asia/Kolkata", instant)!;
    expect(special.today).toBe("Open today 12:00–15:00");
  });

  it("lists all seven days with unset days closed, and survives an unknown zone", () => {
    const summary = summariseHours({ weekly, exceptions: {} }, "Not/AZone", instant)!;
    expect(summary.week).toHaveLength(7);
    expect(summary.week.find((row) => row.day === "Tuesday")?.hours).toBe("Closed");
    expect(summary.week.find((row) => row.day === "Saturday")?.hours).toBe("10:00–16:00");
  });
});
