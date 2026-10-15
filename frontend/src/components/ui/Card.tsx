import type { PropsWithChildren } from "react";

export type CardProps = PropsWithChildren<{
  className?: string;
  padding?: "sm" | "md";
}>;

export function Card({ children, className = "", padding = "md" }: CardProps) {
  const paddingClass = padding === "sm" ? "p-3" : "p-5";

  return (
    <div
      className={`desk-panel ${paddingClass} ${className}`}
    >
      {children}
    </div>
  );
}
