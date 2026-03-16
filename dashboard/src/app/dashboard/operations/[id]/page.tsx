import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Layers, Logs, ShieldAlert } from "lucide-react";
import { Header } from "@/components/header";
import { AutoRefresh } from "@/components/auto-refresh";
import { EntriesTable } from "@/components/entries-table";
import { Pagination } from "@/components/pagination";
import { StageTree } from "@/components/stage-tree";
import { SubjectsTable } from "@/components/subjects-table";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getOperationTrace, getOperationsV2 } from "@/lib/queries";
import { formatDate } from "@/lib/utils";
import { RelationChip } from "@/components/relation-chip";
import { OperationTimeline } from "@/components/operation-timeline";
import { PayloadComparePanel } from "@/components/payload-compare-panel";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}

const TABS = [
  { id: "timeline", label: "Timeline" },
  { id: "requests", label: "Requests" },
  { id: "responses", label: "Responses" },
  { id: "logs", label: "Logs" },
  { id: "errors", label: "Errors" },
];

function entryKindsForTab(tab: string) {
  switch (tab) {
    case "requests":
      return ["http_request", "external_request"];
    case "responses":
      return ["http_response", "external_response"];
    case "logs":
      return ["app_log"];
    case "errors":
      return ["error"];
    default:
      return undefined;
  }
}

export default async function OperationDetailPage({ params, searchParams }: Props) {
  const [{ id }, sp] = await Promise.all([params, searchParams]);
  const activeTab = TABS.some((tab) => tab.id === sp.tab) ? String(sp.tab) : "timeline";
  const sort = sp.sort === "desc" ? "desc" : "asc";
  const page = sp.page ? Number(sp.page) : 1;
  const trace = await getOperationTrace(id, {
    page,
    pageSize: 25,
    timelinePage: sp.timelinePage ? Number(sp.timelinePage) : 1,
    timelinePageSize: 250,
    entryKinds: entryKindsForTab(activeTab),
    sortDirection: sort,
  });

  if (!trace.operation) {
    notFound();
  }
  const operation = trace.operation;

  const relatedOperations = operation.batch_id
    ? await getOperationsV2({ batch_id: operation.batch_id, page: 1, pageSize: 6 })
    : null;

  return (
    <>
      <Header title={`Operación ${operation.operation_key}`} description={operation.route}>
        <AutoRefresh />
        <Link href="/dashboard/operations">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
            Volver
          </Button>
        </Link>
      </Header>

      <div className="space-y-6">
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Investigación rápida</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Estado</div>
                <div className="mt-2"><StatusBadge status={operation.operation_status} /></div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Inicio</div>
                <div className="mt-2 text-sm">{formatDate(operation.started_at)}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Duración</div>
                <div className="mt-2 text-sm font-mono">{operation.duration_ms != null ? `${operation.duration_ms.toLocaleString()} ms` : "—"}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">HTTP</div>
                <div className="mt-2 text-sm font-mono">{operation.http_status_code ?? "—"}</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5">
              <RelationChip label="batch" value={operation.batch_id} href={operation.batch_id ? `/dashboard/batches/${encodeURIComponent(operation.batch_id)}` : null} tone="warning" />
              <RelationChip label="errors" value={operation.error_count} tone={operation.error_count > 0 ? "danger" : "default"} />
              <RelationChip label="busy" value={operation.context_busy_count} tone="warning" />
              <RelationChip label="conflict" value={operation.context_conflict_count} tone="danger" />
              <RelationChip label="released" value={operation.context_release_count} tone="info" />
              <RelationChip label="finalized" value={operation.context_finalize_count} tone="success" />
              <RelationChip label="repairs" value={operation.pending_repair_count} tone={operation.pending_repair_count > 0 ? "danger" : "success"} />
            </div>

            {operation.error_message && (
              <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-200">
                {operation.error_message}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <Card className="border-border/60">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Timeline</CardTitle>
              <div className="flex items-center gap-2 text-xs">
                <Link href={`/dashboard/operations/${operation.operation_id}?tab=timeline&sort=asc`} className={`rounded-full px-3 py-1 ${sort === "asc" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
                  asc
                </Link>
                <Link href={`/dashboard/operations/${operation.operation_id}?tab=timeline&sort=desc`} className={`rounded-full px-3 py-1 ${sort === "desc" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
                  desc
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <OperationTimeline items={trace.timeline.rows} />
              <Pagination page={trace.timeline.page} totalPages={trace.timeline.totalPages} total={trace.timeline.total} />
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card className="border-border/60">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Layers className="h-4 w-4" aria-hidden="true" />
                  Context lifecycle
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-1.5">
                <RelationChip label="busy" value={operation.context_busy_count} tone="warning" />
                <RelationChip label="conflict" value={operation.context_conflict_count} tone="danger" />
                <RelationChip label="released" value={operation.context_release_count} tone="info" />
                <RelationChip label="finalized" value={operation.context_finalize_count} tone="success" />
              </CardContent>
            </Card>

            <Card className="border-border/60">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <ShieldAlert className="h-4 w-4" aria-hidden="true" />
                  Persistencia y repairs
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-1.5">
                <RelationChip label="repair errors" value={operation.repair_error_count} tone={operation.repair_error_count > 0 ? "danger" : "success"} />
                <RelationChip label="pending repairs" value={operation.pending_repair_count} tone={operation.pending_repair_count > 0 ? "danger" : "success"} />
                <RelationChip label="related ops" value={operation.related_operation_count} tone="info" />
              </CardContent>
            </Card>

            {relatedOperations && (
              <Card className="border-border/60">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Logs className="h-4 w-4" aria-hidden="true" />
                    Operaciones relacionadas
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {relatedOperations.rows.filter((operation) => operation.operation_id !== trace.operation?.operation_id).map((operation) => (
                    <Link key={operation.operation_id} href={`/dashboard/operations/${operation.operation_id}`} className="block rounded-2xl border border-border/60 bg-background/40 p-3 hover:border-primary/30 hover:bg-background/60 transition-colors">
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <div className="text-sm font-semibold">{operation.operation_key}</div>
                          <div className="text-[11px] text-muted-foreground">{operation.route}</div>
                        </div>
                        <RelationChip label="status" value={operation.operation_status} tone={operation.error_count > 0 ? "danger" : "success"} />
                      </div>
                    </Link>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Sujetos</CardTitle>
          </CardHeader>
          <CardContent>
            <SubjectsTable subjects={trace.subjects} />
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Etapas</CardTitle>
          </CardHeader>
          <CardContent>
            <StageTree stages={trace.stages} />
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <CardTitle className="text-base">Entradas</CardTitle>
            <div className="flex flex-wrap gap-2">
              {TABS.map((tab) => (
                <Link
                  key={tab.id}
                  href={`/dashboard/operations/${operation.operation_id}?tab=${tab.id}&sort=${sort}`}
                  className={`rounded-full px-3 py-1.5 text-xs ${tab.id === activeTab ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"}`}
                >
                  {tab.label}
                </Link>
              ))}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <PayloadComparePanel entries={trace.entries.rows} />
            <EntriesTable entries={trace.entries.rows} />
            <Pagination page={trace.entries.page} totalPages={trace.entries.totalPages} total={trace.entries.total} />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
