"use client";

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface TooltipProps {
    content: string;
    children: ReactNode;
    side?: "top" | "bottom";
    className?: string;
}

export function Tooltip({ content, children, side = "top", className }: TooltipProps) {
    return (
        <span className={cn("relative inline-flex group", className)}>
            {children}
            <span
                className={cn(
                    "pointer-events-none absolute left-1/2 -translate-x-1/2 z-50",
                    "rounded-md bg-foreground px-2.5 py-1.5 text-[11px] font-medium text-background leading-tight",
                    "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100",
                    "transition-opacity duration-150 whitespace-nowrap",
                    "shadow-lg",
                    side === "top" && "bottom-full mb-2",
                    side === "bottom" && "top-full mt-2",
                )}
                role="tooltip"
            >
                {content}
                <span
                    className={cn(
                        "absolute left-1/2 -translate-x-1/2 h-1.5 w-1.5 rotate-45 bg-foreground",
                        side === "top" && "top-full -mt-0.5",
                        side === "bottom" && "bottom-full -mb-0.5",
                    )}
                    aria-hidden="true"
                />
            </span>
        </span>
    );
}
