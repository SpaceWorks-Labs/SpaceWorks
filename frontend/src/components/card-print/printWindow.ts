// Shared print shell (parity §5.1): opens a window at the card's real size and prints it. The shell is
// generic (event badges, staff and member cards): it takes already-rendered DOM nodes laid out in millimetres,
// copies the page's styles into the window and sets `@page` to the stock, so the printer driver gets the exact
// paper size. It persists nothing; receipts are a separate hook (usePrintReceipts).

export type PrintStock = { widthMm: number; heightMm: number };
/** `per_card`: one card per page (card and label printers). `sheet`: cards flow on the paper at `stock`. */
export type PrintLayout = "per_card" | "sheet";
export type PrintResult = "printed" | "blocked";

/** CSS pixels per millimetre: a print window renders 96 CSS px per inch, so this draws a card at true size. */
export const PX_PER_MM = 96 / 25.4;
const SETTLE_MS = 2000;

export function printCss(stock: PrintStock, layout: PrintLayout = "per_card") {
  const page = `@page { size: ${stock.widthMm}mm ${stock.heightMm}mm; margin: 0 }`;
  const sheet = layout === "sheet" ? "" : `.card-print-page { width: ${stock.widthMm}mm; height: ${stock.heightMm}mm; page-break-after: always; break-after: page; overflow: hidden }
.card-print-page:last-child { page-break-after: auto; break-after: auto }`;
  return `${page}
html, body { margin: 0; padding: 0; background: #fff }
* { -webkit-print-color-adjust: exact; print-color-adjust: exact }
${sheet}`;
}

function copyStyles(target: Document) {
  document.querySelectorAll("style, link[rel='stylesheet']").forEach((node) => {
    target.head.appendChild(target.importNode(node, true));
  });
}

/** Resolves once every image and font is ready, or after `SETTLE_MS` so a slow asset never blocks the desk. */
function settled(target: Document) {
  const images = Array.from(target.images).filter((image) => !image.complete)
    .map((image) => new Promise<void>((done) => { image.onload = image.onerror = () => done(); }));
  const fonts = target.fonts?.ready ?? Promise.resolve();
  return Promise.race([Promise.all([fonts, ...images]).then(() => undefined),
    new Promise<void>((done) => window.setTimeout(done, SETTLE_MS))]);
}

/**
 * Prints `nodes` (each already sized in mm, e.g. a badge drawn at PX_PER_MM) at the stock size.
 * Returns "blocked" when the browser refuses the window, so the desk can tell the operator.
 */
export async function printNodes(nodes: HTMLElement[], stock: PrintStock, options: { layout?: PrintLayout; title?: string } = {}): Promise<PrintResult> {
  const win = window.open("", "_blank", `width=${Math.round(stock.widthMm * PX_PER_MM) + 40},height=${Math.round(stock.heightMm * PX_PER_MM) + 80}`);
  if (!win) return "blocked";
  const doc = win.document;
  doc.title = options.title ?? "";
  copyStyles(doc);
  const style = doc.createElement("style");
  style.textContent = printCss(stock, options.layout);
  doc.head.appendChild(style);
  nodes.forEach((node) => {
    const page = doc.createElement("div");
    page.className = "card-print-page";
    page.appendChild(doc.importNode(node, true));
    doc.body.appendChild(page);
  });
  await settled(doc);
  win.focus();
  win.print();
  win.addEventListener("afterprint", () => win.close());
  return "printed";
}
