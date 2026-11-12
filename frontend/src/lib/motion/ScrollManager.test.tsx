import { act, render } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ScrollManager } from "./ScrollManager";

let go: ReturnType<typeof useNavigate>;
function Grab() { go = useNavigate(); return null; }

function setup(initial = "/") {
  render(<MemoryRouter initialEntries={[initial]}><ScrollManager /><Grab /><div id="faq" /></MemoryRouter>);
}

describe("ScrollManager", () => {
  const scrollTo = vi.fn();
  beforeEach(() => {
    window.sessionStorage.clear();
    scrollTo.mockReset();
    vi.stubGlobal("scrollTo", scrollTo);
    Object.defineProperty(window, "scrollY", { value: 0, writable: true, configurable: true });
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("opens a new page at the top", () => {
    setup("/");
    window.scrollY = 1800;
    act(() => { go("/features"); });
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, left: 0, behavior: "instant" });
  });

  it("returns to where the page was left on back", () => {
    setup("/");
    window.scrollY = 1200;
    act(() => { go("/features"); });
    window.scrollY = 300;
    act(() => { go(-1); });
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 1200, left: 0, behavior: "instant" });
  });

  it("keeps the position when only the query string changes", () => {
    setup("/spaces");
    window.scrollY = 640;
    act(() => { go("/spaces?city=kochi"); });
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it("scrolls to a section for a hash link", () => {
    setup("/");
    const into = vi.fn();
    const target = document.getElementById("faq") as HTMLElement;
    target.scrollIntoView = into;
    act(() => { go("/#faq"); });
    expect(into).toHaveBeenCalledWith({ block: "start" });
  });

  it("never throws when session storage is unavailable", () => {
    setup("/");
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(() => act(() => { go("/docs"); })).not.toThrow();
    spy.mockRestore();
  });
});
