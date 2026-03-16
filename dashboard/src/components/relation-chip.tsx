"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";

interface RelationChipProps {
  label: string;
  value: string | number | boolean | null | undefined;
  href?: string | null;
  tone?: "default" | "danger" | "warning" | "info" | "success";
}

const TONE_STYLES: Record<NonNullable<RelationChipProps["tone"]>, string> = {
  default: "border-border/60 bg-muted/30 text-foreground/80",
  danger: "border-rose-500/20 bg-rose-500/10 text-rose-300",
  warning: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  info: "border-sky-500/20 bg-sky-500/10 text-sky-300",
  success: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
};

export function RelationChip({ label, value, href, tone = "default" }: RelationChipProps) {
  if (value == null || value === "") {
    return null;
  }

  const content = (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-medium tracking-wide",
        TONE_STYLES[tone],
      )}
    >
      <span className="uppercase text-foreground/45">{label}</span>
      <span className="font-mono normal-case text-[11px]">{String(value)}</span>
    </span>
  );

  if (!href) {
    return content;
  }

  return (
    <Link href={href} className="transition-transform duration-150 hover:-translate-y-0.5">
      {content}
    </Link>
  );
}
