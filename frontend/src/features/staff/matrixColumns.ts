/**
 * Column classes for wide DataTable matrices (notification channels, recipient mutes, reports).
 * DataTable already stacks rows on phones and scrolls sideways from md up; these keep the row
 * label pinned while it scrolls, and turn a stacked toggle cell into one "Label ..... [x]" line.
 */
export const STICKY_FIRST_COLUMN = [
  "md:sticky md:left-0 md:z-[1] md:bg-panel md:shadow-[inset_-1px_0_0_rgb(var(--color-line))]",
  "md:[thead_&]:bg-surface dark:md:[thead_&]:bg-hover",
].join(" ");

export const MATRIX_TOGGLE_CELL = "max-md:flex max-md:items-center max-md:justify-between max-md:gap-3 md:text-center";
