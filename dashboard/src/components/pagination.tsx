"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface PaginationProps {
  page: number;
  totalPages: number;
  total: number;
}

export function Pagination({ page, totalPages, total }: PaginationProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  function go(p: number) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", String(p));
    router.push(`${pathname}?${params.toString()}`);
  }

  function getPageNumbers(): (number | "dots")[] {
    const pages: (number | "dots")[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      const start = Math.max(2, page - 1);
      const end = Math.min(totalPages - 1, page + 1);
      if (start > 2) pages.push("dots");
      for (let i = start; i <= end; i++) pages.push(i);
      if (end < totalPages - 1) pages.push("dots");
      pages.push(totalPages);
    }
    return pages;
  }

  if (totalPages <= 1 && total === 0) return null;

  return (
    <nav className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-6 animate-fade-in" aria-label="Paginación">
      <p className="text-sm text-muted-foreground tabular-nums">
        <span className="font-semibold text-foreground">{total.toLocaleString()}</span>{" "}
        resultado{total !== 1 ? "s" : ""}
      </p>
      <div className="flex items-center gap-1.5">
        <Button
          variant="outline"
          size="sm"
          onClick={() => go(page - 1)}
          disabled={page <= 1}
          className="h-8 w-8 p-0"
          aria-label="Página anterior"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        </Button>

        {getPageNumbers().map((p, i) =>
          p === "dots" ? (
            <span key={`dots-${i}`} className="px-1.5 text-muted-foreground/50 text-sm select-none" aria-hidden="true">
              …
            </span>
          ) : (
            <button
              key={p}
              onClick={() => go(p)}
              disabled={p === page}
              className={cn(
                "h-8 w-8 rounded-lg text-xs font-medium transition-all duration-150",
                p === page
                  ? "bg-primary text-primary-foreground cursor-default shadow-glow"
                  : "hover:bg-muted text-muted-foreground hover:text-foreground",
              )}
              aria-label={`Página ${p}`}
              aria-current={p === page ? "page" : undefined}
            >
              {p}
            </button>
          ),
        )}

        <Button
          variant="outline"
          size="sm"
          onClick={() => go(page + 1)}
          disabled={page >= totalPages}
          className="h-8 w-8 p-0"
          aria-label="Página siguiente"
        >
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
}
