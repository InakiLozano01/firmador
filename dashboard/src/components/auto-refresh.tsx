"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useCallback } from "react";
import { RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

const INTERVALS = [
    { label: "5s", ms: 5000 },
    { label: "15s", ms: 15000 },
    { label: "30s", ms: 30000 },
    { label: "60s", ms: 60000 },
];

export function AutoRefresh() {
    const router = useRouter();
    const [active, setActive] = useState(false);
    const [intervalMs, setIntervalMs] = useState(15000);
    const [showMenu, setShowMenu] = useState(false);
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const menuRef = useRef<HTMLDivElement>(null);

    const stopTimer = useCallback(() => {
        if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
        }
    }, []);

    const startTimer = useCallback(() => {
        stopTimer();
        timerRef.current = setInterval(() => {
            router.refresh();
        }, intervalMs);
    }, [intervalMs, router, stopTimer]);

    useEffect(() => {
        if (active) startTimer();
        else stopTimer();
        return stopTimer;
    }, [active, startTimer, stopTimer]);

    // Close menu on outside click
    useEffect(() => {
        function handleClick(e: MouseEvent) {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
                setShowMenu(false);
            }
        }
        if (showMenu) document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, [showMenu]);

    return (
        <div className="relative" ref={menuRef}>
            <button
                onClick={() => setActive((a) => !a)}
                className={cn(
                    "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all duration-200",
                    active
                        ? "border-primary/30 bg-primary/10 text-primary shadow-glow"
                        : "border-input bg-background text-muted-foreground hover:text-foreground hover:border-primary/20",
                )}
                title={active ? `Auto-refresh activo (${INTERVALS.find(i => i.ms === intervalMs)?.label})` : "Activar auto-refresh"}
            >
                <RefreshCw
                    className={cn(
                        "h-3.5 w-3.5 transition-transform",
                        active && "animate-spin-slow",
                    )}
                    aria-hidden="true"
                />
                <span className="hidden sm:inline">
                    {active ? `On · ${INTERVALS.find(i => i.ms === intervalMs)?.label}` : "Auto"}
                </span>
            </button>

            {active && (
                <button
                    onClick={() => setShowMenu((s) => !s)}
                    className="ml-1 rounded-md px-1.5 py-1.5 text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                    title="Cambiar intervalo"
                >
                    ▾
                </button>
            )}

            {showMenu && (
                <div className="absolute right-0 top-full mt-1.5 z-50 rounded-lg border border-border bg-card p-1 shadow-lg animate-scale-in min-w-[90px]">
                    {INTERVALS.map((opt) => (
                        <button
                            key={opt.ms}
                            onClick={() => {
                                setIntervalMs(opt.ms);
                                setShowMenu(false);
                            }}
                            className={cn(
                                "flex w-full items-center rounded-md px-3 py-1.5 text-xs transition-colors",
                                opt.ms === intervalMs
                                    ? "bg-primary/10 text-primary font-medium"
                                    : "text-foreground hover:bg-muted",
                            )}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
