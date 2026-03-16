import { Suspense } from "react";
import Link from "next/link";
import { Header } from "@/components/header";
import { AutoRefresh } from "@/components/auto-refresh";
import { Filters } from "@/components/filters";
import { Pagination } from "@/components/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getRepairBacklog } from "@/lib/queries";
import { RelationChip } from "@/components/relation-chip";
import { formatDate } from "@/lib/utils";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | undefined>>;
}

async function RepairsContent({ searchParams }: Props) {
  const params = await searchParams;
  const repairs = await getRepairBacklog({
    status: params.status,
    batch_id: params.batch_id,
    page: params.page ? Number(params.page) : 1,
    pageSize: 25,
  });

  return (
    <>
      <Filters statuses={["pending", "recovered", "failed"]} showStatusSelect showBatchSearch />
      <div className="space-y-4">
        {repairs.rows.map((repair) => (
          <Card key={repair.manifest_id} className="border-border/60">
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
                <div>
                  <div>{repair.id_doc ? `Documento ${repair.id_doc}` : repair.operation_key ?? "Repair manifest"}</div>
                  <div className="text-[11px] font-normal text-muted-foreground">{formatDate(repair.created_at)}</div>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <RelationChip label="status" value={repair.status} tone={repair.status === "pending" ? "danger" : repair.status === "failed" ? "warning" : "success"} />
                  <RelationChip label="retry" value={repair.retryable} tone={repair.retryable ? "success" : "danger"} />
                  <RelationChip label="batch" value={repair.batch_id} href={repair.batch_id ? `/dashboard/batches/${encodeURIComponent(repair.batch_id)}` : null} tone="warning" />
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Operation</div>
                  {repair.operation_id ? <Link href={`/dashboard/operations/${repair.operation_id}`} className="font-mono text-primary hover:underline underline-offset-2">{repair.operation_key}</Link> : <span className="text-muted-foreground">—</span>}
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Payload sha</div>
                  <div className="font-mono text-xs break-all">{repair.payload_sha256}</div>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Target path</div>
                  <div className="font-mono text-xs break-all text-muted-foreground">{repair.target_path}</div>
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Manifest path</div>
                  <div className="font-mono text-xs break-all text-muted-foreground">{repair.manifest_path}</div>
                </div>
              </div>
              {repair.last_error && (
                <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-200">
                  {repair.last_error}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
      <Pagination page={repairs.page} totalPages={repairs.totalPages} total={repairs.total} />
    </>
  );
}

export default function RepairsPage(props: Props) {
  return (
    <>
      <Header title="Repairs" description="Repair manifests, promotion failures y recuperaciones">
        <AutoRefresh />
      </Header>
      <Suspense fallback={<Skeleton className="h-96 rounded-lg" />}>
        <RepairsContent searchParams={props.searchParams} />
      </Suspense>
    </>
  );
}
