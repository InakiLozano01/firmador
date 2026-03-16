"use client";

import { Braces } from "lucide-react";

interface AttrsPanelProps {
  attrs: Record<string, unknown> | null | undefined;
}

export function AttrsPanel({ attrs }: AttrsPanelProps) {
  const meaningfulAttrs = attrs && Object.keys(attrs).length > 0 ? attrs : null;
  if (!meaningfulAttrs) {
    return null;
  }

  return (
    <details className="group rounded-lg border border-border/50 bg-background/40 p-2">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-[11px] font-medium text-muted-foreground">
        <Braces className="h-3.5 w-3.5" aria-hidden="true" />
        Attrs
      </summary>
      <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border/40 bg-background/80 p-3 text-[11px] leading-5 text-foreground/85 font-mono">
        {JSON.stringify(meaningfulAttrs, null, 2)}
      </pre>
    </details>
  );
}
