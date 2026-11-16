import {
  ArrowLeft, ArrowRight, ArrowUpRight, ArrowUp, ArrowDown, ArrowUpDown, Calendar, Check, CheckCircle, ChevronDown,
  Circle, CircleAlert, Clock, Ellipsis, Info, LoaderCircle, Plus, Search,
  Settings, TriangleAlert, User, Wrench, X, Lock, Mail, KeyRound, Building2,
  ShieldCheck, ShieldAlert, Compass, Eye, EyeOff, MapPin, Cog, Printer, HardHat, Send, CircleSlash,
} from "lucide-react";
const icons = { ArrowLeft, ArrowRight, ArrowUpRight, ArrowUp, ArrowDown, ArrowUpDown, Calendar, Check, CheckCircle, ChevronDown,
  Circle, CircleAlert, Clock, Ellipsis, Info, LoaderCircle, Plus, Search,
  Settings, TriangleAlert, User, Wrench, X, Lock, Mail, KeyRound, Building2,
  ShieldCheck, ShieldAlert, Compass, Eye, EyeOff, MapPin, Cog, Printer, HardHat, Send, CircleSlash };
export type IconName = keyof typeof icons;
export type IconProps = { name: IconName; className?: string };
export function Icon({ name, className = "" }: IconProps) {
  const Glyph = icons[name];
  return <Glyph aria-hidden="true" size={24} strokeWidth={2} className={`shrink-0 ${className}`} />;
}
