import { BoxArt } from "../BoxSpinner";

export type SkeletonProps = { className?: string };
export type SkeletonRowsProps = { rows?: number; cols: number };
/** A decorative loading placeholder: the Space Works box (callers announce the loading state themselves). */
export function Skeleton({ className = "" }: SkeletonProps) {
  return <div className={`grid place-items-center ${className}`} aria-hidden="true"><BoxArt size={20} /></div>;
}

export function SkeletonRows({ rows = 5, cols }: SkeletonRowsProps) {
  return (
    <>
      {Array.from({ length: rows }, (_, rowIndex) => (
        <tr role="row" key={rowIndex} className="block md:table-row">
          {Array.from({ length: cols }, (_, colIndex) => (
            <td role="cell" key={colIndex} className="block px-3 py-2 md:table-cell">
              <Skeleton className="h-4 w-full" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
