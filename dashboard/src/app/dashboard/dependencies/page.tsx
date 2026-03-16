import { Suspense } from "react";
import { Header } from "@/components/header";
import { AutoRefresh } from "@/components/auto-refresh";
import { Filters } from "@/components/filters";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EntriesTable } from "@/components/entries-table";
import { Pagination } from "@/components/pagination";
import { getDependencySummary, getDistinctDependencies, getEntries } from "@/lib/queries";
import { RelationChip } from "@/components/relation-chip";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | undefined>>;
}

async function DependenciesContent({ searchParams }: Props) {
  const params = await searchParams;
  const [summary, dependencies, entries] = await Promise.all([
    getDependencySummary(),
    getDistinctDependencies(),
    getEntries({
      dependency: params.dependency,
      page: params.page ? Number(params.page) : 1,
      pageSize: 25,
      sortDirection: "desc",
    }),
  ]);

  return (
    <>
      <Filters dependencies={dependencies} showDependencySelect />
      <div className="grid gap-4 xl:grid-cols-2">
        {summary
          .filter((dependency) => !params.dependency || dependency.dependency === params.dependency)
          .map((dependency) => (
            <Card key={dependency.dependency} className="border-border/60">
              <CardHeader>
                <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
                  <span>{dependency.dependency}</span>
                  <RelationChip label="errors" value={dependency.error_count} tone={dependency.error_count > 0 ? "danger" : "success"} />
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-1.5">
                  <RelationChip label="events" value={dependency.entry_count} />
                  <RelationChip label="avg" value={dependency.avg_duration_ms ? `${dependency.avg_duration_ms} ms` : "—"} tone="info" />
                  <RelationChip label="p95" value={dependency.p95_duration_ms ? `${dependency.p95_duration_ms} ms` : "—"} tone="warning" />
                </div>
                <div className="rounded-xl border border-border/60 bg-background/40 p-3">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Status codes</div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {Object.entries(dependency.status_codes).map(([statusCode, count]) => (
                      <RelationChip key={statusCode} label={statusCode} value={count} />
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
      </div>

      <Card className="mt-6 border-border/60">
        <CardHeader>
          <CardTitle className="text-base">Eventos de dependencia</CardTitle>
        </CardHeader>
        <CardContent>
          <EntriesTable entries={entries.rows} />
          <Pagination page={entries.page} totalPages={entries.totalPages} total={entries.total} />
        </CardContent>
      </Card>
    </>
  );
}

export default function DependenciesPage(props: Props) {
  return (
    <>
      <Header title="Dependencies" description="DSS, locks y otras dependencias desde la traza enriquecida">
        <AutoRefresh />
      </Header>
      <Suspense fallback={<Skeleton className="h-96 rounded-lg" />}>
        <DependenciesContent searchParams={props.searchParams} />
      </Suspense>
    </>
  );
}
