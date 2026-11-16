import { renderHook, act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { printCss, printNodes } from "./printWindow";
import { usePrintReceipts } from "./usePrintReceipts";

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("printCss", () => {
  it("sets @page to the stock with no margin", () => {
    expect(printCss({ widthMm: 101.6, heightMm: 152.4 })).toContain("@page { size: 101.6mm 152.4mm; margin: 0 }");
  });
  it("breaks pages per card only for the per-card layout", () => {
    expect(printCss({ widthMm: 90, heightMm: 55 }, "per_card")).toContain("page-break-after: always");
    expect(printCss({ widthMm: 90, heightMm: 55 }, "sheet")).not.toContain("page-break-after");
  });
});

describe("printNodes", () => {
  it("reports blocked when the browser refuses the window", async () => {
    vi.spyOn(window, "open").mockReturnValue(null);
    expect(await printNodes([document.createElement("div")], { widthMm: 90, heightMm: 55 })).toBe("blocked");
  });
  it("prints one page per node in the opened window", async () => {
    const doc = document.implementation.createHTMLDocument("print");
    const print = vi.fn();
    vi.spyOn(window, "open").mockReturnValue({ document: doc, focus: vi.fn(), print, close: vi.fn(), addEventListener: vi.fn() } as unknown as Window);
    const result = await printNodes([document.createElement("div"), document.createElement("div")], { widthMm: 90, heightMm: 55 });
    expect(result).toBe("printed");
    expect(doc.querySelectorAll(".card-print-page")).toHaveLength(2);
    expect(print).toHaveBeenCalledOnce();
  });
});

describe("usePrintReceipts", () => {
  it("sends a receipt with a fresh uuid when online", async () => {
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(true);
    const send = vi.fn().mockResolvedValue({}), queue = vi.fn();
    const { result } = renderHook(() => usePrintReceipts<{ registration_id: number }>({ send, queue }));
    let outcome = "";
    await act(async () => { outcome = await result.current.record({ registration_id: 5 }); });
    expect(outcome).toBe("sent");
    expect(send.mock.calls[0][0]).toMatchObject({ registration_id: 5, operation_id: expect.stringMatching(/^[0-9a-f-]{36}$/) });
    expect(queue).not.toHaveBeenCalled();
  });
  it("queues the receipt when the network is down", async () => {
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    const send = vi.fn(), queue = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => usePrintReceipts<{ registration_id: number }>({ send, queue }));
    let outcome = "";
    await act(async () => { outcome = await result.current.record({ registration_id: 5 }); });
    expect(outcome).toBe("queued");
    expect(send).not.toHaveBeenCalled();
    expect(queue).toHaveBeenCalledOnce();
  });
});
