import Link from "next/link";
import { notFound } from "next/navigation";
import { Header } from "@/components/header";
import { AutoRefresh } from "@/components/auto-refresh";
import { EntriesTable } from "@/components/entries-table";
import { SubjectsTable } from "@/components/subjects-table";
import { Pagination } from "@/components/pagination";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getBatchTrace } from "@/lib/queries";
import { RelationChip } from "@/components/relation-chip";
import { formatDate } from "@/lib/utils";
import { PayloadComparePanel } from "@/components/payload-compare-panel";
import { ArrowLeft } from "lucide-react";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ batchId: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}

export default async function BatchDetailPage({ params, searchParams }: Props) {
  const [{ batchId }, sp] = await Promise.all([params, searchParams]);
  const trace = await getBatchTrace(decodeURIComponent(batchId), {
    page: sp.page ? Number(sp.page) : 1,
    pageSize: 25,
    entryPage: sp.entryPage ? Number(sp.entryPage) : 1,
    entryPageSize: 50,
  });

  if (!trace.summary) {
    notFound();
  }

  return (
    <>
      <Header title={`Batch ${trace.summary.batch_id}`} description="Correlación completa del batch">
        <AutoRefresh />
        <Link href="/dashboard/batches">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
            Volver
          </Button>
        </Link>
      </Header>

      <div className="space-y-6">
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Resumen</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div className="text-sm">Primero: <span className="text-muted-foreground">{formatDate(trace.summary.first_seen_at)}</span></div>
              <div className="text-sm">Último: <span className="text-muted-foreground">{formatDate(trace.summary.last_seen_at)}</span></div>
              <div className="text-sm">Operaciones: <span className="text-muted-foreground">{trace.summary.operation_count}</span></div>
              <div className="text-sm">Errores: <span className="text-muted-foreground">{trace.summary.error_count}</span></div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <RelationChip label="docs" value={trace.summary.document_count} />
              <RelationChip label="exp" value={trace.summary.expediente_count} />
              <RelationChip label="repairs" value={trace.summary.pending_repair_count} tone={trace.summary.pending_repair_count > 0 ? "danger" : "success"} />
              <RelationChip label="busy" value={trace.summary.max_context_busy_count} tone="warning" />
              <RelationChip label="conflict" value={trace.summary.max_context_conflict_count} tone="danger" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Operaciones relacionadas</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {trace.operations.rows.map((operation) => (
              <Link key={operation.operation_id} href={`/dashboard/operations/${operation.operation_id}`} className="block rounded-2xl border border-border/60 bg-background/40 p-4 hover:border-primary/30 hover:bg-background/60 transition-colors">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold">{operation.operation_key}</div>
                    <div className="text-[11px] text-muted-foreground">{operation.route}</div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <RelationChip label="status" value={operation.operation_status} tone={operation.error_count > 0 ? "danger" : "success"} />
                    <RelationChip label="errors" value={operation.error_count} tone={operation.error_count > 0 ? "danger" : "default"} />
                    <RelationChip label="repairs" value={operation.pending_repair_count} tone={operation.pending_repair_count > 0 ? "danger" : "success"} />
                  </div>
                </div>
              </Link>
            ))}
            <Pagination page={trace.operations.page} totalPages={trace.operations.totalPages} total={trace.operations.total} />
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Sujetos relacionados</CardTitle>
          </CardHeader>
          <CardContent>
            <SubjectsTable subjects={trace.subjects.rows} />
            <Pagination page={trace.subjects.page} totalPages={trace.subjects.totalPages} total={trace.subjects.total} />
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Entradas recientes del batch</CardTitle>
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
