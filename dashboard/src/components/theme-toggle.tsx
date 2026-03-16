"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
    const [dark, setDark] = useState(true);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
        setDark(document.documentElement.classList.contains("dark"));
    }, []);

    function toggle() {
        const next = !dark;
        setDark(next);
        document.documentElement.classList.toggle("dark", next);
        document.documentElement.classList.toggle("light", !next);
        document.documentElement.style.colorScheme = next ? "dark" : "light";
        localStorage.setItem("theme", next ? "dark" : "light");
    }

    if (!mounted) return <div className="h-8 w-8" />;

    return (
        <button
            onClick={toggle}
            className="group h-8 w-8 rounded-lg flex items-center justify-center text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-white/[0.06] active:scale-90 transition-all duration-200"
            aria-label={dark ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
            title={dark ? "Modo claro" : "Modo oscuro"}
        >
            <span className="transition-transform duration-300 group-hover:rotate-12">
                {dark ? (
                    <Sun className="h-4 w-4" />
                ) : (
                    <Moon className="h-4 w-4" />
                )}
            </span>
        </button>
    );
}
