export type SkeletonProps = { className?: string };
export type SkeletonRowsProps = { rows?: number; cols: number };
export function Skeleton({ className = "" }: SkeletonProps) {
  return <div className={`motion-safe:animate-pulse rounded-control bg-line ${className}`} aria-hidden="true" />;
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
