import { Suspense } from "react";
import Link from "next/link";
import { Header } from "@/components/header";
import { AutoRefresh } from "@/components/auto-refresh";
import { Filters } from "@/components/filters";
import { Pagination } from "@/components/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getBatchSummaries } from "@/lib/queries";
import { RelationChip } from "@/components/relation-chip";
import { formatDate } from "@/lib/utils";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | undefined>>;
}

async function BatchesContent({ searchParams }: Props) {
  const params = await searchParams;
  const batches = await getBatchSummaries({
    batch_id: params.batch_id,
    page: params.page ? Number(params.page) : 1,
    pageSize: 25,
  });

  return (
    <>
      <Filters showBatchSearch />
      <div className="grid gap-4 xl:grid-cols-2">
        {batches.rows.map((batch) => (
          <Link key={batch.batch_id} href={`/dashboard/batches/${encodeURIComponent(batch.batch_id)}`} className="block">
            <Card className="h-full border-border/60 hover:border-primary/30 transition-colors">
              <CardHeader>
                <CardTitle className="flex items-center justify-between gap-3 text-base">
                  <code className="text-xs font-mono">{batch.batch_id}</code>
                  <RelationChip label="errors" value={batch.error_count} tone={batch.error_count > 0 ? "danger" : "default"} />
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="text-xs text-muted-foreground">Primero: {formatDate(batch.first_seen_at)}</div>
                  <div className="text-xs text-muted-foreground">Último: {formatDate(batch.last_seen_at)}</div>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <RelationChip label="ops" value={batch.operation_count} />
                  <RelationChip label="docs" value={batch.document_count} />
                  <RelationChip label="exp" value={batch.expediente_count} />
                  <RelationChip label="repairs" value={batch.pending_repair_count} tone={batch.pending_repair_count > 0 ? "danger" : "success"} />
                  <RelationChip label="busy" value={batch.max_context_busy_count} tone="warning" />
                  <RelationChip label="conflict" value={batch.max_context_conflict_count} tone="danger" />
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
      <Pagination page={batches.page} totalPages={batches.totalPages} total={batches.total} />
    </>
  );
}

export default function BatchesPage(props: Props) {
  return (
    <>
      <Header title="Batches" description="Correlación de operaciones, documentos y expedientes por batch_id">
        <AutoRefresh />
      </Header>
      <Suspense fallback={<Skeleton className="h-96 rounded-lg" />}>
        <BatchesContent searchParams={props.searchParams} />
      </Suspense>
    </>
  );
}
