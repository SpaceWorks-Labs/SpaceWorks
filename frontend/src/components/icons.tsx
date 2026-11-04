import { ChartColumn, Moon, Sun, User } from "lucide-react";

type IconProps = {
  className?: string;
};

export function ChartIcon({ className }: IconProps) {
  return <ChartColumn aria-hidden="true" focusable="false" className={className} size={20} strokeWidth={2} />;
}

export function MoonIcon({ className }: IconProps) {
  return <Moon aria-hidden="true" focusable="false" className={className} size={20} strokeWidth={2} />;
}

export function SunIcon({ className }: IconProps) {
  return <Sun aria-hidden="true" focusable="false" className={className} size={20} strokeWidth={2} />;
}

export function UserIcon({ className }: IconProps) {
  return <User aria-hidden="true" focusable="false" className={className} size={20} strokeWidth={2} />;
}
