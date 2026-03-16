import { Badge } from "@/components/ui/badge";

const STATUS_MAP: Record<string, { variant: "success" | "destructive" | "warning" | "secondary" | "default" | "info"; label?: string }> = {
  ok: { variant: "success" },
  completed: { variant: "success" },
  success: { variant: "success" },
  error: { variant: "destructive" },
  failed: { variant: "destructive" },
  partial_error: { variant: "warning", label: "partial_error" },
  rejected: { variant: "warning" },
  warning: { variant: "warning" },
  info: { variant: "info" },
  debug: { variant: "secondary" },
  started: { variant: "default" },
  running: { variant: "default" },
  skipped: { variant: "secondary" },
};

const DOT_COLORS: Record<string, string> = {
  success: "bg-emerald-500",
  destructive: "bg-rose-500",
  warning: "bg-amber-500",
  default: "bg-blue-500",
  secondary: "bg-slate-400",
  info: "bg-sky-500",
};

const DESCRIPTIONS: Record<string, string> = {
  ok: "Operación exitosa",
  completed: "Completado",
  success: "Éxito",
  error: "Error",
  failed: "Falló",
  partial_error: "Error parcial",
  rejected: "Rechazado",
  warning: "Advertencia",
  info: "Información",
  debug: "Debug",
  started: "Iniciado",
  running: "En ejecución",
  skipped: "Omitido",
};

export function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_MAP[status] ?? { variant: "secondary" as const };
  const dotColor = DOT_COLORS[cfg.variant] ?? "bg-slate-400";
  const description = DESCRIPTIONS[status] ?? status;

  return (
    <Badge variant={cfg.variant} className="gap-1.5" title={description}>
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${dotColor} ${cfg.variant === "destructive" ? "animate-pulse-dot" : ""
          } ${cfg.variant === "default" ? "animate-pulse-dot" : ""}`}
        aria-hidden="true"
      />
      {cfg.label ?? status}
    </Badge>
  );
}
