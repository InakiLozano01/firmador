import { Suspense } from "react";
import Link from "next/link";
import { getOverviewStatsV2 } from "@/lib/queries";
import { Header } from "@/components/header";
import { AutoRefresh } from "@/components/auto-refresh";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EntriesTable } from "@/components/entries-table";
import { Skeleton } from "@/components/ui/skeleton";
import { RelationChip } from "@/components/relation-chip";
import { Activity, AlertTriangle, DatabaseZap, Repeat, ShieldAlert, TimerReset, Waves } from "lucide-react";

export const dynamic = "force-dynamic";

async function OverviewContent() {
  const stats = await getOverviewStatsV2();
  const primaryRuntime = stats.runtime_status[0] ?? null;
  const cards = [
    { title: "Operaciones 24h", value: stats.total_operations_24h.toLocaleString(), icon: Activity, tone: "sky" },
    { title: "Errores 24h", value: stats.error_count_24h.toLocaleString(), icon: AlertTriangle, tone: "rose" },
    { title: "Retries 24h", value: stats.retry_count_24h.toLocaleString(), icon: TimerReset, tone: "amber" },
    { title: "Repairs pendientes", value: stats.pending_repair_count.toLocaleString(), icon: ShieldAlert, tone: "rose" },
    { title: "Context conflicts", value: stats.context_conflict_count.toLocaleString(), icon: Repeat, tone: "teal" },
    { title: "Queue depth", value: String(primaryRuntime?.queue_depth ?? 0), icon: DatabaseZap, tone: "emerald" },
  ] as const;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <Card key={card.title} className="overflow-hidden border-border/60 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.06),transparent_55%),linear-gradient(180deg,rgba(255,255,255,0.02),rgba(255,255,255,0.01))]">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{card.title}</CardTitle>
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-border/60 bg-background/70">
                <card.icon className="h-4 w-4 text-foreground/80" aria-hidden="true" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-semibold tracking-tight tabular-nums">{card.value}</div>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.25fr_0.95fr]">
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Etapas críticas</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {stats.slow_stages.map((stage, index) => (
              <div key={stage.stage_key} className="rounded-2xl border border-border/60 bg-background/40 p-4 stagger-row" style={{ animationDelay: `${index * 40}ms` }}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <code className="rounded-lg bg-muted px-2 py-1 text-xs font-mono">{stage.stage_key}</code>
                  <div className="flex flex-wrap gap-1.5">
                    <RelationChip label="avg" value={`${stage.avg_ms.toLocaleString()} ms`} tone="info" />
                    <RelationChip label="p95" value={`${stage.p95_ms.toLocaleString()} ms`} tone="warning" />
                    <RelationChip label="max" value={`${stage.max_ms.toLocaleString()} ms`} tone="danger" />
                  </div>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted/50">
                  <div className="h-full rounded-full bg-[linear-gradient(90deg,#f59e0b_0%,#fb7185_100%)]" style={{ width: `${Math.min(100, Math.max(8, stage.p95_ms / 10))}%` }} />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Salud del recorder</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {stats.runtime_status.length === 0 ? (
              <div className="text-sm text-muted-foreground">No hay heartbeat del runtime.</div>
            ) : (
              stats.runtime_status.map((runtime) => (
                <div key={runtime.service_name} className="rounded-2xl border border-border/60 bg-background/40 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-semibold">{runtime.service_name}</div>
                      <div className="text-[11px] text-muted-foreground">{runtime.instance_id ?? "sin instancia"}</div>
                    </div>
                    <RelationChip label="flush" value={runtime.last_flush_at ? "ok" : "idle"} tone={runtime.last_flush_at ? "success" : "warning"} />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <RelationChip label="queue" value={runtime.queue_depth} tone={runtime.queue_depth > 0 ? "warning" : "success"} />
                    <RelationChip label="dropped" value={runtime.dropped_events} tone={runtime.dropped_events > 0 ? "danger" : "success"} />
                    <RelationChip label="repair backlog" value={String(runtime.attrs?.repair_backlog_size ?? 0)} tone="warning" />
                    <RelationChip label="vault" value={String(runtime.attrs?.payload_vault_enabled ?? false)} tone="info" />
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-3">
        <Card className="border-border/60 xl:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Dependencias</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {stats.dependency_summary.map((dependency) => (
              <Link key={dependency.dependency} href={`/dashboard/dependencies?dependency=${encodeURIComponent(dependency.dependency)}`} className="block rounded-2xl border border-border/60 bg-background/40 p-4 hover:border-primary/30 hover:bg-background/60 transition-colors">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold">{dependency.dependency}</div>
                    <div className="text-[11px] text-muted-foreground">último evento {dependency.last_seen_at ? new Date(dependency.last_seen_at).toLocaleString("es-AR") : "—"}</div>
                  </div>
                  <RelationChip label="errors" value={dependency.error_count} tone={dependency.error_count > 0 ? "danger" : "success"} />
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <RelationChip label="events" value={dependency.entry_count} />
                  <RelationChip label="avg" value={dependency.avg_duration_ms ? `${dependency.avg_duration_ms} ms` : "—"} tone="info" />
                  <RelationChip label="p95" value={dependency.p95_duration_ms ? `${dependency.p95_duration_ms} ms` : "—"} tone="warning" />
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border/60 xl:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Batches en observación</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {stats.batch_watchlist.map((batch) => (
              <Link key={batch.batch_id} href={`/dashboard/batches/${encodeURIComponent(batch.batch_id)}`} className="block rounded-2xl border border-border/60 bg-background/40 p-4 hover:border-primary/30 hover:bg-background/60 transition-colors">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <code className="text-xs font-mono">{batch.batch_id}</code>
                  <RelationChip label="errors" value={batch.error_count} tone={batch.error_count > 0 ? "danger" : "default"} />
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <RelationChip label="ops" value={batch.operation_count} />
                  <RelationChip label="docs" value={batch.document_count} />
                  <RelationChip label="exp" value={batch.expediente_count} />
                  <RelationChip label="repairs" value={batch.pending_repair_count} tone={batch.pending_repair_count > 0 ? "danger" : "success"} />
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border/60 xl:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Repair feed</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {stats.critical_repairs.map((repair) => (
              <Link key={repair.manifest_id} href="/dashboard/repairs" className="block rounded-2xl border border-border/60 bg-background/40 p-4 hover:border-primary/30 hover:bg-background/60 transition-colors">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold">{repair.id_doc ? `Documento ${repair.id_doc}` : repair.operation_key ?? "repair"}</div>
                    <div className="text-[11px] text-muted-foreground">{new Date(repair.created_at).toLocaleString("es-AR")}</div>
                  </div>
                  <RelationChip label="status" value={repair.status} tone={repair.status === "pending" ? "danger" : "success"} />
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <RelationChip label="batch" value={repair.batch_id} tone="warning" />
                  <RelationChip label="retry" value={repair.retryable} tone={repair.retryable ? "success" : "danger"} />
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>
      </section>

      <Card className="border-border/60">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Incidentes recientes</CardTitle>
          <Link href="/dashboard/failures" className="text-xs text-primary hover:underline underline-offset-2">
            Ver investigación completa
          </Link>
        </CardHeader>
        <CardContent>
          <EntriesTable entries={stats.recent_errors} />
        </CardContent>
      </Card>

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle className="text-base">Errores por etapa</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {stats.top_error_stages.map((stage, index) => (
            <div key={stage.stage_key} className="rounded-2xl border border-border/60 bg-background/40 p-4 stagger-row" style={{ animationDelay: `${index * 40}ms` }}>
              <div className="flex items-center justify-between gap-3">
                <code className="text-xs font-mono">{stage.stage_key}</code>
                <span className="text-sm font-semibold tabular-nums">{stage.cnt}</span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted/50">
                <div className="h-full rounded-full bg-[linear-gradient(90deg,#fb7185_0%,#f97316_100%)]" style={{ width: `${Math.min(100, Math.max(8, stage.cnt * 10))}%` }} />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-28 rounded-lg" />
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.95fr]">
        <Skeleton className="h-80 rounded-lg" />
        <Skeleton className="h-80 rounded-lg" />
      </div>
      <Skeleton className="h-96 rounded-lg" />
    </div>
  );
}

export default function OverviewPage() {
  return (
    <>
      <Header title="Console" description="Operación, contexto, dependencias, repairs y payload vault desde PostgreSQL">
        <AutoRefresh />
        <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-card/50 px-3 py-1.5 text-xs text-muted-foreground">
          <Waves className="h-3.5 w-3.5" aria-hidden="true" />
          Next-only observability
        </div>
      </Header>
      <Suspense fallback={<LoadingSkeleton />}>
        <OverviewContent />
      </Suspense>
    </>
  );
}
