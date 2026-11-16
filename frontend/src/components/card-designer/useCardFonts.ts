// Load every font family/weight the given documents use (the designer, the template gallery).
import { useEffect, useMemo } from "react";

import type { CardDocument } from "./cardTypes";
import { loadCardFont } from "./fontLoader";

export function fontKeys(documents: CardDocument[]) {
  return [...new Set(documents.flatMap((document) => [...document.front.layers, ...document.back.layers])
    .filter((layer) => layer.font_family).map((layer) => `${layer.font_family}|${layer.font_weight ?? 400}`))].sort();
}

export function useCardFonts(designId: number, documents: CardDocument[]) {
  const keys = useMemo(() => fontKeys(documents).join(","), [documents]);
  useEffect(() => {
    if (!keys) return;
    keys.split(",").forEach((key) => { const [family, weight] = key.split("|"); void loadCardFont(designId, family, Number(weight)); });
  }, [designId, keys]);
}
