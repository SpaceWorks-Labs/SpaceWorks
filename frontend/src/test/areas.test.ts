// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("node:child_process", () => ({ spawnSync: vi.fn() }));
import { spawnSync } from "node:child_process";
import { areas, main, pathsForAreas } from "./areas";

beforeEach(() => vi.resetAllMocks());

describe("test areas", () => {
  it("selects the feature directories and shared shell/permission tests", () => {
    expect(pathsForAreas(["events"])).toEqual([
      "src/App", "src/cloudEdge", "src/components", "src/edgeSecurity", "src/features/events",
      "src/features/staff", "src/lib", "src/sw", "src/test",
    ]);
    expect(pathsForAreas(["events"])).not.toContain("src/features/bookings");
  });

  it("unions and deduplicates areas deterministically", () => {
    const result = pathsForAreas(["bookings", "events", "events"]);
    expect(result).toEqual(pathsForAreas(["events", "bookings"]));
    expect(result).toContain("src/features/bookings");
    expect(result).toContain("src/features/events");
    expect(result.filter(path => path === "src/features/staff")).toHaveLength(1);
  });

  it("rejects absent, unknown and inherited object keys", () => {
    expect(() => pathsForAreas([])).toThrow("Supply at least one area; use --list");
    expect(() => pathsForAreas(["eventz"])).toThrow("Unknown areas: eventz; use --list");
    expect(() => pathsForAreas(["toString"])).toThrow("Unknown areas: toString; use --list");
  });

  it("has directory ownership for every area", () => {
    for (const paths of Object.values(areas)) expect(paths.length).toBeGreaterThan(0);
  });

  it("passes selected paths and extra arguments without a command shell", () => {
    vi.mocked(spawnSync).mockReturnValue({ status: 0 } as ReturnType<typeof spawnSync>);
    expect(main(["events, bookings", "--maxWorkers=2"])).toBe(0);
    expect(spawnSync).toHaveBeenCalledExactlyOnceWith(process.execPath, [
      expect.stringMatching(/frontend[\\/]node_modules[\\/]vitest[\\/]vitest\.mjs$/),
      "run", ...pathsForAreas(["events", "bookings"]), "--maxWorkers=2",
    ], { cwd: expect.stringMatching(/frontend[\\/]?$/), stdio: "inherit" });
  });

  it("preserves vitest failures and signals", () => {
    vi.mocked(spawnSync).mockReturnValue({ status: 1 } as ReturnType<typeof spawnSync>);
    expect(main(["events"])).toBe(1);
    vi.mocked(spawnSync).mockReturnValue({ status: null } as ReturnType<typeof spawnSync>);
    expect(main(["events"])).toBe(1);
  });

  it("fails before spawning for unknown areas", () => {
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(main(["eventz"])).toBe(2);
    expect(log).toHaveBeenCalledWith("Unknown areas: eventz; use --list");
    expect(spawnSync).not.toHaveBeenCalled();
    log.mockRestore();
  });

  it("lists areas without running tests", () => {
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    expect(main(["--list"])).toBe(0);
    expect(log).toHaveBeenCalledExactlyOnceWith(Object.keys(areas).sort().join("\n"));
    expect(spawnSync).not.toHaveBeenCalled();
    log.mockRestore();
  });
});
