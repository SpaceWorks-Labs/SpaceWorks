/**
 * G-code and DXF to a plain top-view SVG drawing (GAP2 M5, #142 OQ-12). Pure and bounded, run in
 * the preview worker. Only the geometry is read -- never slicer settings, never a file reference --
 * and the output uses svg/g/path/circle elements alone, so it passes the shared `safeSvg` check.
 * Binary DXF and anything without drawable geometry is refused ("preview unavailable").
 */
export const MAX_SEGMENTS = 500_000;
type Point = [number, number];
type Shapes = { paths: Point[][]; circles: [number, number, number][] };

const round = (value: number) => Math.round(value * 1000) / 1000;

function toSvg({ paths, circles }: Shapes, stroke: string) {
  const xs: number[] = [], ys: number[] = [];
  for (const path of paths) for (const [x, y] of path) { xs.push(x); ys.push(y); }
  for (const [x, y, r] of circles) { xs.push(x - r, x + r); ys.push(y - r, y + r); }
  if (!xs.length) throw new Error("No drawable geometry.");
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const x of xs) { minX = Math.min(minX, x); maxX = Math.max(maxX, x); }
  for (const y of ys) { minY = Math.min(minY, y); maxY = Math.max(maxY, y); }
  const width = Math.max(maxX - minX, 1e-3), height = Math.max(maxY - minY, 1e-3), pad = Math.max(width, height) * 0.02;
  const line = Math.max(width, height) / 400;
  // y grows upwards in machine space and downwards in SVG: mirror inside one group.
  const body = paths.filter(path => path.length > 1).map(path =>
    `<path d="M${path.map(([x, y]) => `${round(x)} ${round(y)}`).join(" L")}"/>`).join("")
    + circles.map(([x, y, r]) => `<circle cx="${round(x)}" cy="${round(y)}" r="${round(r)}"/>`).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${round(minX - pad)} ${round(-maxY - pad)} ${round(width + 2 * pad)} ${round(height + 2 * pad)}">`
    + `<g transform="scale(1 -1)" fill="none" stroke="${stroke}" stroke-width="${round(line)}" stroke-linecap="round" stroke-linejoin="round">${body}</g></svg>`;
}

function finite(...values: number[]) {
  if (values.some(value => !Number.isFinite(value) || Math.abs(value) > 1e9)) throw new Error("Invalid coordinates.");
}

/** Cutting and extruding moves of a G-code file, seen from above. Travel moves are left out. */
export function gcodeToSvg(text: string, stroke: string) {
  const extrudes = /^\s*G0?1\b[^;]*\bE-?\d/im.test(text);
  let absolute = true, scale = 1, x = 0, y = 0, e = 0, relativeE = false, segments = 0;
  const paths: Point[][] = [];
  let current: Point[] | null = null;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.replace(/;.*$|\(.*?\)/g, "").trim().toUpperCase();
    if (!line) continue;
    const words = Object.fromEntries([...line.matchAll(/([A-Z])\s*(-?\d*\.?\d+)/g)].map(([, key, value]) => [key, Number(value)]));
    const g = /\bG0*(\d+)\b/.exec(line)?.[1];
    if (g === "90") absolute = true;
    else if (g === "91") absolute = false;
    else if (g === "20") scale = 25.4;
    else if (g === "21") scale = 1;
    else if (g === "92" && words.E !== undefined) e = words.E;
    if (/\bM83\b/.test(line)) relativeE = true;
    if (/\bM82\b/.test(line)) relativeE = false;
    if (!["0", "1", "2", "3"].includes(g ?? "")) continue;
    const nx = words.X === undefined ? x : (absolute ? 0 : x) + words.X * scale;
    const ny = words.Y === undefined ? y : (absolute ? 0 : y) + words.Y * scale;
    finite(nx, ny);
    let draws = g !== "0";
    if (extrudes && draws) {
      const delta = words.E === undefined ? 0 : relativeE ? words.E : words.E - e;
      if (words.E !== undefined && !relativeE) e = words.E;
      draws = delta > 0;
    }
    if (draws && (nx !== x || ny !== y)) {
      if (!current) { current = [[x, y]]; paths.push(current); }
      current.push([nx, ny]);
      if (++segments > MAX_SEGMENTS) throw new Error("Toolpath exceeds the preview limit.");
    } else if (nx !== x || ny !== y) current = null;
    x = nx; y = ny;
  }
  return toSvg({ paths, circles: [] }, stroke);
}

function entities(text: string) {
  const lines = text.split(/\r?\n/);
  if (lines.length < 4 || text.startsWith("AutoCAD Binary DXF")) throw new Error("Only text DXF files can be previewed.");
  const pairs: [number, string][] = [];
  for (let i = 0; i + 1 < lines.length; i += 2) pairs.push([Number(lines[i].trim()), lines[i + 1].trim()]);
  const start = pairs.findIndex(([code, value], i) => code === 2 && value === "ENTITIES" && pairs[i - 1]?.[1] === "SECTION");
  if (start < 0) throw new Error("No drawing in this DXF.");
  const rows: { type: string; codes: [number, string][] }[] = [];
  for (let i = start + 1; i < pairs.length; i++) {
    const [code, value] = pairs[i];
    if (code !== 0) { rows.at(-1)?.codes.push(pairs[i]); continue; }
    if (value === "ENDSEC") break;
    rows.push({ type: value, codes: [] });
    if (rows.length > MAX_SEGMENTS) throw new Error("Drawing exceeds the preview limit.");
  }
  return rows;
}

const num = (codes: [number, string][], code: number, fallback = 0) => {
  const found = codes.find(([key]) => key === code);
  return found ? Number(found[1]) : fallback;
};
const points = (codes: [number, string][]) => {
  const out: Point[] = [];
  for (const [code, value] of codes) {
    if (code === 10) out.push([Number(value), 0]);
    else if (code === 20 && out.length) out[out.length - 1][1] = Number(value);
  }
  out.forEach(([x, y]) => finite(x, y));
  return out;
};

function arc(cx: number, cy: number, r: number, from: number, to: number): Point[] {
  const sweep = ((to - from) % 360 + 360) % 360 || 360, steps = Math.max(8, Math.ceil(sweep / 6));
  return Array.from({ length: steps + 1 }, (_, i) => {
    const angle = (from + (sweep * i) / steps) * Math.PI / 180;
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)] as Point;
  });
}

/** Lines, polylines, circles, arcs and spline control points of an ASCII DXF, seen from above. */
export function dxfToSvg(text: string, stroke: string) {
  const shapes: Shapes = { paths: [], circles: [] };
  let polyline: { closed: boolean; points: Point[] } | null = null;
  for (const { type, codes } of entities(text)) {
    if (type === "LINE") {
      const a: Point = [num(codes, 10), num(codes, 20)], b: Point = [num(codes, 11), num(codes, 21)];
      finite(...a, ...b); shapes.paths.push([a, b]);
    } else if (type === "LWPOLYLINE" || type === "SPLINE") {
      const vertices = points(codes);
      if (num(codes, 70) & 1 && vertices.length) vertices.push(vertices[0]);
      shapes.paths.push(vertices);
    } else if (type === "POLYLINE") polyline = { closed: Boolean(num(codes, 70) & 1), points: [] };
    else if (type === "VERTEX" && polyline) polyline.points.push(...points(codes));
    else if (type === "SEQEND" && polyline) {
      if (polyline.closed && polyline.points.length) polyline.points.push(polyline.points[0]);
      shapes.paths.push(polyline.points); polyline = null;
    } else if (type === "CIRCLE") {
      const circle: [number, number, number] = [num(codes, 10), num(codes, 20), num(codes, 40)];
      finite(...circle); if (circle[2] > 0) shapes.circles.push(circle);
    } else if (type === "ARC") {
      const values = [num(codes, 10), num(codes, 20), num(codes, 40), num(codes, 50), num(codes, 51)];
      finite(...values); if (values[2] > 0) shapes.paths.push(arc(values[0], values[1], values[2], values[3], values[4]));
    }
  }
  return toSvg(shapes, stroke);
}
