/** Domain-neutral print coordinates, measured from the page's top-left corner. */
export type PositionedElement = {
  field: string;
  x_mm: number;
  y_mm: number;
  width_mm: number;
  height_mm: number;
  font: "sans" | "serif";
  font_size_pt: number;
  bold: boolean;
  align: "left" | "center" | "right";
  colour: string;
};

export function defaultElement(field: string, index: number, width: number, height: number): PositionedElement {
  const lineHeight = Math.min(10, height - 4);
  return { field, x_mm: 2, y_mm: Math.min(2 + index * lineHeight, height - lineHeight - 2),
    width_mm: Math.max(1, width - 4), height_mm: lineHeight, font: "sans",
    font_size_pt: field === "name" ? 18 : 10, bold: field === "name", align: "center", colour: "#111111" };
}

export function syncElements(fields: string[], elements: PositionedElement[], width: number, height: number) {
  return fields.map((field, index) => elements.find((item) => item.field === field)
    ?? defaultElement(field, index, width, height));
}

export function snapMillimetres(value: number, grid: number, maximum: number, minimum = 0) {
  const step = Math.max(0.1, grid);
  return Math.max(minimum, Math.min(maximum, Number((Math.round(value / step) * step).toFixed(2))));
}

export function layoutFits(elements: PositionedElement[], width: number, height: number) {
  return elements.every((element) => Number.isFinite(element.x_mm) && Number.isFinite(element.y_mm)
    && element.x_mm >= 0 && element.y_mm >= 0 && element.width_mm > 0 && element.height_mm > 0
    && element.x_mm + element.width_mm <= width && element.y_mm + element.height_mm <= height);
}
