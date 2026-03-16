import Link from "next/link";
import type { SubjectSummary } from "@/lib/queries";
import { StatusBadge } from "@/components/status-badge";
import { RelationChip } from "@/components/relation-chip";
import { formatDate } from "@/lib/utils";
import { Inbox } from "lucide-react";

interface SubjectsTableProps {
  subjects: SubjectSummary[];
}

export function SubjectsTable({ subjects }: SubjectsTableProps) {
  if (subjects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground animate-fade-in">
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/60 border border-border/50">
          <Inbox className="h-6 w-6 text-muted-foreground/40" aria-hidden="true" />
        </div>
        <p className="text-sm font-medium">No se encontraron sujetos</p>
        <p className="text-xs text-muted-foreground/60 mt-1">Modificá los filtros para ver más resultados</p>
      </div>
    );
  }

  return (
    <>
      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto rounded-lg border border-border bg-card animate-slide-up">
        <table className="w-full text-sm table-striped">
          <thead>
            <tr className="border-b bg-muted/40">
              <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Inicio</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Tipo</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Clave</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Estado</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Operación</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Batch</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Ruta</th>
              <th className="px-4 py-3 text-right text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">ms</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {subjects.map((subject, index) => {
              const href = subject.subject_type === "document"
                ? `/dashboard/documents/${encodeURIComponent(subject.subject_key)}`
                : `/dashboard/expedientes/${encodeURIComponent(subject.subject_key)}`;
              const isError = subject.subject_status === "error" || subject.subject_status === "failed";

              return (
                <tr
                  key={`${subject.operation_id}-${subject.subject_id}`}
                  className={`hover:bg-muted/40 transition-colors stagger-row ${isError ? "border-l-2 border-l-destructive/50" : ""}`}
                  style={{ animationDelay: `${index * 20}ms` }}
                >
                  <td className="px-4 py-2.5 whitespace-nowrap text-xs text-muted-foreground tabular-nums">
                    {formatDate(subject.started_at)}
                  </td>
                  <td className="px-4 py-2.5">
                    <code className="rounded-md bg-muted px-1.5 py-0.5 text-xs font-mono">
                      {subject.subject_type}
                    </code>
                  </td>
                  <td className="px-4 py-2.5 text-xs font-mono">
                    <Link href={href} className="text-primary hover:underline underline-offset-2">
                      {subject.subject_key}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={subject.subject_status} />
                  </td>
                  <td className="px-4 py-2.5 text-xs font-mono">
                    <Link href={`/dashboard/operations/${subject.operation_id}`} className="text-primary hover:underline underline-offset-2">
                      {subject.operation_key}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-xs">
                    <RelationChip label="batch" value={subject.batch_id} href={subject.batch_id ? `/dashboard/batches/${encodeURIComponent(subject.batch_id)}` : null} tone="warning" />
                  </td>
                  <td className="px-4 py-2.5 text-xs">
                    <code className="rounded-md bg-muted px-1.5 py-0.5">{subject.route}</code>
                  </td>
                  <td className="px-4 py-2.5 text-right text-xs font-mono tabular-nums">
                    {subject.duration_ms != null ? subject.duration_ms.toLocaleString() : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-3 animate-slide-up">
        {subjects.map((subject, index) => {
          const href = subject.subject_type === "document"
            ? `/dashboard/documents/${encodeURIComponent(subject.subject_key)}`
            : `/dashboard/expedientes/${encodeURIComponent(subject.subject_key)}`;
          const isError = subject.subject_status === "error" || subject.subject_status === "failed";

          return (
            <div
              key={`m-${subject.operation_id}-${subject.subject_id}`}
              className={`rounded-xl border bg-card p-4 space-y-2 stagger-row ${isError ? "border-l-2 border-l-destructive/50" : "border-border"}`}
              style={{ animationDelay: `${index * 30}ms` }}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <code className="rounded-md bg-muted px-1.5 py-0.5 text-xs font-mono">{subject.subject_type}</code>
                  <StatusBadge status={subject.subject_status} />
                </div>
                <span className="text-[10px] text-muted-foreground tabular-nums">{formatDate(subject.started_at)}</span>
              </div>
              <Link href={href} className="block text-xs text-primary font-mono hover:underline underline-offset-2">
                {subject.subject_key}
              </Link>
              <div className="flex items-center justify-between gap-2 pt-1 border-t border-border/40 text-xs">
                <Link href={`/dashboard/operations/${subject.operation_id}`} className="text-primary font-mono hover:underline underline-offset-2">
                  {subject.operation_key}
                </Link>
                <span className="font-mono text-muted-foreground tabular-nums">
                  {subject.duration_ms != null ? `${subject.duration_ms.toLocaleString()} ms` : "—"}
                </span>
              </div>
              <RelationChip label="batch" value={subject.batch_id} href={subject.batch_id ? `/dashboard/batches/${encodeURIComponent(subject.batch_id)}` : null} tone="warning" />
            </div>
          );
        })}
      </div>
    </>
  );
}
