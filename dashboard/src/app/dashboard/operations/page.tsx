import { Suspense } from "react";
import Link from "next/link";
import { ArrowRight, Clock } from "lucide-react";
import { Header } from "@/components/header";
import { AutoRefresh } from "@/components/auto-refresh";
import { Filters } from "@/components/filters";
import { Pagination } from "@/components/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/utils";
import { getDistinctOperationKeys, getOperationsV2 } from "@/lib/queries";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | undefined>>;
}

async function OperationsContent({ searchParams }: Props) {
  const params = await searchParams;
  const [operations, operationKeys] = await Promise.all([
    getOperationsV2({
      status: params.status,
      operation_key: params.operation_key,
      batch_id: params.batch_id,
      from: params.from,
      to: params.to,
      page: params.page ? Number(params.page) : 1,
      pageSize: 25,
    }),
    getDistinctOperationKeys(),
  ]);

  return (
    <>
      <Filters
        operationKeys={operationKeys}
        statuses={["running", "success", "partial_error", "failed", "rejected"]}
        showOperationKeySelect
        showStatusSelect
        showBatchSearch
      />

      {operations.rows.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground animate-fade-in">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/60 border border-border/50">
            <Clock className="h-6 w-6 text-muted-foreground/40" aria-hidden="true" />
          </div>
          <p className="text-sm font-medium">No se encontraron operaciones</p>
          <p className="text-xs text-muted-foreground/60 mt-1">Ajustá los filtros o esperá a que se generen nuevas operaciones</p>
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto rounded-lg border border-border bg-card animate-slide-up">
            <table className="w-full text-sm table-striped">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Inicio</th>
                  <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Clave</th>
                  <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Ruta</th>
                  <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Estado</th>
                  <th className="px-4 py-3 text-right text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">HTTP</th>
                  <th className="px-4 py-3 text-right text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Errores</th>
                  <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Batch</th>
                  <th className="px-4 py-3 text-right text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Sujetos</th>
                  <th className="px-4 py-3 text-right text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">ms</th>
                  <th className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"><span className="sr-only">Ver</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {operations.rows.map((operation, index) => {
                  const isError = operation.operation_status === "failed" || operation.error_count > 0;
                  return (
                    <tr
                      key={operation.operation_id}
                      className={`hover:bg-muted/40 transition-colors stagger-row ${isError ? "border-l-2 border-l-destructive/50" : ""}`}
                      style={{ animationDelay: `${index * 20}ms` }}
                    >
                      <td className="px-4 py-2.5 whitespace-nowrap text-xs text-muted-foreground tabular-nums">
                        {formatDate(operation.started_at)}
                      </td>
                      <td className="px-4 py-2.5 text-xs font-mono font-medium">{operation.operation_key}</td>
                      <td className="px-4 py-2.5 text-xs">
                        <code className="rounded-md bg-muted px-1.5 py-0.5">{operation.route}</code>
                      </td>
                      <td className="px-4 py-2.5">
                        <StatusBadge status={operation.operation_status} />
                      </td>
                      <td className="px-4 py-2.5 text-right text-xs font-mono tabular-nums">
                        {operation.http_status_code ?? "—"}
                      </td>
                      <td className="px-4 py-2.5 text-right text-xs font-mono tabular-nums">
                        <span className={operation.error_count > 0 ? "text-rose-400 font-semibold" : ""}>
                          {operation.error_count.toLocaleString()}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-xs font-mono">
                        {operation.batch_id ? (
                          <Link href={`/dashboard/batches/${encodeURIComponent(operation.batch_id)}`} className="text-amber-300 hover:underline underline-offset-2">
                            {operation.batch_id}
                          </Link>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right text-xs font-mono tabular-nums">
                        {operation.subject_count.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right text-xs font-mono tabular-nums">
                        {operation.duration_ms != null ? operation.duration_ms.toLocaleString() : "—"}
                      </td>
                      <td className="px-4 py-2.5">
                        <Link href={`/dashboard/operations/${operation.operation_id}`} className="inline-flex items-center gap-1 text-xs text-primary hover:underline underline-offset-2 group/link">
                          Ver
                          <ArrowRight className="h-3 w-3 group-hover/link:translate-x-0.5 transition-transform" aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-3 animate-slide-up">
            {operations.rows.map((operation, index) => {
              const isError = operation.operation_status === "failed" || operation.error_count > 0;
              return (
                <Link
                  key={`m-${operation.operation_id}`}
                  href={`/dashboard/operations/${operation.operation_id}`}
                  className={`block rounded-xl border bg-card p-4 space-y-2 stagger-row hover:bg-muted/30 transition-colors ${isError ? "border-l-2 border-l-destructive/50" : "border-border"}`}
                  style={{ animationDelay: `${index * 30}ms` }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-mono font-medium">{operation.operation_key}</span>
                    <StatusBadge status={operation.operation_status} />
                  </div>
                  <code className="block rounded-md bg-muted px-1.5 py-0.5 text-xs w-fit">{operation.route}</code>
                  <div className="flex items-center justify-between gap-2 pt-1 border-t border-border/40 text-[10px] text-muted-foreground">
                    <span className="tabular-nums">{formatDate(operation.started_at)}</span>
                    <div className="flex items-center gap-3 tabular-nums font-mono">
                      {operation.error_count > 0 && <span className="text-rose-400">{operation.error_count} err</span>}
                      {operation.batch_id && <span className="text-amber-300">{operation.batch_id}</span>}
                      <span>{operation.duration_ms != null ? `${operation.duration_ms.toLocaleString()}ms` : "—"}</span>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
          <Pagination page={operations.page} totalPages={operations.totalPages} total={operations.total} />
        </>
      )}
    </>
  );
}

export default function OperationsPage(props: Props) {
  return (
    <>
      <Header title="Operaciones" description="Operaciones HTTP y trazas V2">
        <AutoRefresh />
      </Header>
      <Suspense fallback={<Skeleton className="h-96 rounded-lg" />}>
        <OperationsContent searchParams={props.searchParams} />
      </Suspense>
    </>
  );
}
