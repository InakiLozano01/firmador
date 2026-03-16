"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FileText,
  FolderOpen,
  AlertTriangle,
  Cog,
  Layers3,
  HardDriveUpload,
  Network,
  LogOut,
  X,
  Menu,
} from "lucide-react";
import { useState, useEffect } from "react";
import { ThemeToggle } from "@/components/theme-toggle";

const links = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/batches", label: "Batches", icon: Layers3 },
  { href: "/dashboard/repairs", label: "Repairs", icon: HardDriveUpload },
  { href: "/dashboard/dependencies", label: "Dependencies", icon: Network },
  { href: "/dashboard/documents", label: "Documentos", icon: FileText },
  { href: "/dashboard/expedientes", label: "Expedientes", icon: FolderOpen },
  { href: "/dashboard/operations", label: "Operaciones", icon: Cog },
  { href: "/dashboard/failures", label: "Errores", icon: AlertTriangle },
];

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => { setOpen(false); }, [pathname]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setOpen(true)}
        className="fixed top-3 left-3 z-40 md:hidden flex items-center justify-center h-10 w-10 rounded-lg bg-card border border-border shadow-sm hover:bg-accent active:scale-95 transition-all duration-150"
        aria-label="Abrir menú"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden animate-fade-in"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-60 flex-col bg-sidebar text-sidebar-foreground overflow-hidden",
          "transition-transform duration-200 ease-out",
          "md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* Subtle noise texture */}
        <div className="absolute inset-0 noise-texture pointer-events-none" aria-hidden="true" />

        {/* Ambient glow */}
        <div className="absolute -top-20 -left-20 w-40 h-40 rounded-full bg-primary/5 blur-[60px] pointer-events-none" aria-hidden="true" />

        {/* Header / Logo */}
        <div className="relative flex h-16 items-center justify-between border-b border-white/[0.06] px-4">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl gradient-accent flex items-center justify-center text-xs font-bold text-white tracking-tight shadow-lg shadow-primary/25 hover:scale-105 transition-transform duration-200">
              OD
            </div>
            <div>
              <span className="block text-sm font-semibold tracking-tight leading-tight">
                Obs Dashboard
              </span>
              <span className="block text-[10px] text-white/30 leading-tight">
                Monitoring v2
              </span>
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="md:hidden h-8 w-8 flex items-center justify-center rounded-lg text-white/40 hover:text-white hover:bg-white/[0.06] transition-all duration-150"
            aria-label="Cerrar menú"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Nav */}
        <nav className="relative flex-1 px-3 py-5" aria-label="Navegación principal">
          <p className="px-3 pb-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-white/25">
            Navegación
          </p>
          <ul className="space-y-1">
            {links.map(({ href, label, icon: Icon }) => {
              const active =
                href === "/dashboard"
                  ? pathname === "/dashboard"
                  : pathname.startsWith(href);

              return (
                <li key={href}>
                  <Link
                    href={href}
                    className={cn(
                      "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-150",
                      active
                        ? "bg-white/[0.08] text-white font-medium"
                        : "text-white/45 hover:text-white/85 hover:bg-white/[0.04]",
                    )}
                  >
                    {/* Active indicator bar */}
                    {active && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full gradient-accent animate-scale-in" />
                    )}
                    <Icon className={cn(
                      "h-[18px] w-[18px] shrink-0 transition-all duration-150",
                      active ? "text-sidebar-accent" : "group-hover:text-white/60",
                    )} />
                    {label}
                    {active && (
                      <span className="ml-auto h-1.5 w-1.5 rounded-full bg-sidebar-accent animate-pulse-dot" />
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Footer */}
        <div className="relative border-t border-white/[0.06] p-3 space-y-1">
          <div className="flex items-center justify-between px-3 py-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/25">
              Tema
            </span>
            <ThemeToggle />
          </div>
          <form action="/api/auth/logout" method="POST">
            <button
              type="submit"
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-white/45 hover:text-white/85 hover:bg-white/[0.04] active:scale-[0.98] transition-all duration-150"
            >
              <LogOut className="h-[18px] w-[18px] shrink-0" />
              Cerrar sesión
            </button>
          </form>
        </div>
      </aside>
    </>
  );
}
