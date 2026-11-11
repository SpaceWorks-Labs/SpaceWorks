import { printNodes, type PrintResult } from "../../../components/card-print";
import { staffRequestBlob } from "../../../lib/api";
import type { QueuedPrint } from "./useDeskPrintQueue";

/** Fetches the front (and back) PNG at the chosen stock; the server centres the card on the stock page. */
export async function fetchFaces(facePath: string, stockKey: string, sides: ("front" | "back")[]) {
  const urls: string[] = [];
  try {
    for (const side of sides) {
      const blob = await staffRequestBlob(`${facePath}?side=${side}&stock=${encodeURIComponent(stockKey)}`);
      urls.push(URL.createObjectURL(blob));
    }
  } catch (error) {
    urls.forEach((url) => URL.revokeObjectURL(url));
    throw error;
  }
  return urls;
}

/** Each face becomes one stock-sized page in the shared print window. Works from memory, so it works offline. */
export function printFaces(entry: QueuedPrint): Promise<PrintResult> {
  const nodes = entry.faces.map((url) => {
    const image = document.createElement("img");
    image.src = url;
    image.alt = "";
    image.style.cssText = `display:block;width:${entry.widthMm}mm;height:${entry.heightMm}mm`;
    return image;
  });
  return printNodes(nodes, { widthMm: entry.widthMm, heightMm: entry.heightMm }, { layout: "per_card", title: entry.label });
}
