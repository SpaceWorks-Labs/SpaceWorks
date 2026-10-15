/** A count and its noun, for labels built from live list totals. */
export function plural(count: number, singular: string, multiple = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : multiple}`;
}
