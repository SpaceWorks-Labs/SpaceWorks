/** Keep backend status words while following the product’s sentence-case voice. */
export function machineStatusLabel(status: string) {
  const words = status.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
