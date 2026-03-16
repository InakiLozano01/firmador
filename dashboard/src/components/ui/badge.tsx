import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

export interface BadgeProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info";
}

const variantStyles: Record<string, string> = {
  default: "border-transparent bg-primary/15 text-primary",
  secondary: "border-transparent bg-muted text-muted-foreground",
  destructive: "border-transparent bg-rose-500/15 text-rose-400",
  outline: "text-foreground border-border",
  success: "border-transparent bg-emerald-500/15 text-emerald-400",
  warning: "border-transparent bg-amber-500/15 text-amber-400",
  info: "border-transparent bg-sky-500/15 text-sky-400",
};

const lightOverrides: Record<string, string> = {
  destructive: "bg-rose-100 text-rose-700",
  success: "bg-emerald-100 text-emerald-700",
  warning: "bg-amber-100 text-amber-700",
  info: "bg-sky-100 text-sky-700",
};

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors duration-100",
        variantStyles[variant],
        className,
      )}
      {...props}
    />
  );
}
