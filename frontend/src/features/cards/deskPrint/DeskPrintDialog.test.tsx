import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DeskPrintDialog } from "./DeskPrintDialog";
import { deskStock, stockFamilies } from "./deskStocks";
import { useDeskPrintQueue } from "./useDeskPrintQueue";

const { staffRequestBlob, printNodes } = vi.hoisted(() => ({ staffRequestBlob: vi.fn(), printNodes: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequestBlob }));
vi.mock("../../../components/card-print", () => ({ printNodes }));

beforeEach(() => {
  staffRequestBlob.mockReset(); printNodes.mockReset().mockResolvedValue("printed");
  URL.createObjectURL = vi.fn(() => "blob:face"); URL.revokeObjectURL = vi.fn();
});

describe("desk print stocks (decision 290)", () => {
  it("offers A6, 4x6, 3x4 and CR80 in both orientations", () => {
    expect(stockFamilies().map((family) => family.value)).toEqual(["a6", "4x6", "3x4", "cr80"]);
    expect(deskStock("a6", "portrait")).toMatchObject({ key: "a6-portrait", widthMm: 105, heightMm: 148 });
    expect(deskStock("4x6", "landscape")).toMatchObject({ key: "6x4", widthMm: 152.4, heightMm: 101.6 });
    expect(deskStock("3x4", "landscape").key).toBe("4x3");
    expect(deskStock("cr80", "landscape")).toMatchObject({ key: "cr80-landscape", widthMm: 85.6 });
  });
});

describe("desk print dialog", () => {
  const target = { id: "member:5", label: "Priya TNK-0042", facePath: "/admin/member-cards/5/print-face" };

  function Harness() {
    const queue = useDeskPrintQueue();
    return <DeskPrintDialog target={target} queue={queue} onClose={() => undefined} />;
  }

  it("prints again from memory after the network goes down", async () => {
    staffRequestBlob.mockResolvedValue(new Blob(["png"]));
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Print" }));
    await waitFor(() => expect(printNodes).toHaveBeenCalledTimes(1));
    expect(staffRequestBlob).toHaveBeenCalledWith("/admin/member-cards/5/print-face?side=front&stock=cr80-landscape");
    staffRequestBlob.mockRejectedValue(new Error("offline"));
    fireEvent.click(await screen.findByRole("button", { name: "Print again" }));
    await waitFor(() => expect(printNodes).toHaveBeenCalledTimes(2));
    expect(staffRequestBlob).toHaveBeenCalledTimes(1);
    const [nodes, stock] = printNodes.mock.calls[1];
    expect(nodes).toHaveLength(1);
    expect(stock).toEqual({ widthMm: 85.6, heightMm: 53.98 });
  });

  it("says so when the browser blocks the print window", async () => {
    staffRequestBlob.mockResolvedValue(new Blob(["png"]));
    printNodes.mockResolvedValue("blocked");
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Print" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("blocked the print window");
  });

  it("keeps only the last five printed cards and frees the older faces", () => {
    const { result } = renderHook(() => useDeskPrintQueue());
    act(() => {
      for (let n = 0; n < 7; n += 1) result.current.remember({ id: `c${n}`, label: `c${n}`, stockKey: "4x6", widthMm: 1, heightMm: 1, faces: [`blob:${n}`] });
    });
    expect(result.current.queue).toHaveLength(5);
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2);
  });
});

describe("desk print of several selected cards", () => {
  it("fetches every card's face from the server (so prints are counted) and prints one page per card", async () => {
    staffRequestBlob.mockResolvedValue(new Blob(["png"]));
    const batch = { id: "batch", label: "2 member cards", facePaths: ["/admin/member-cards/5/print-face", "/admin/member-cards/6/print-face"] };
    function Batch() {
      const queue = useDeskPrintQueue();
      return <DeskPrintDialog target={batch} queue={queue} onClose={() => undefined} />;
    }
    render(<Batch />);
    fireEvent.click(screen.getByRole("button", { name: "Print" }));
    await waitFor(() => expect(printNodes).toHaveBeenCalledTimes(1));
    expect(staffRequestBlob).toHaveBeenCalledTimes(2);
    expect(staffRequestBlob).toHaveBeenCalledWith("/admin/member-cards/6/print-face?side=front&stock=cr80-landscape");
    expect(printNodes.mock.calls[0][0]).toHaveLength(2);
    expect(printNodes.mock.calls[0][2]).toMatchObject({ layout: "per_card" });
  });
});
