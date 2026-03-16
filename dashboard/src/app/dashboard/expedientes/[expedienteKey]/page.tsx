import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, FolderOpen } from "lucide-react";
import { EntriesTable } from "@/components/entries-table";
import { Header } from "@/components/header";
import { AutoRefresh } from "@/components/auto-refresh";
import { Pagination } from "@/components/pagination";
import { StageTree } from "@/components/stage-tree";
import { SubjectsTable } from "@/components/subjects-table";
import { RelationChip } from "@/components/relation-chip";
import { PayloadComparePanel } from "@/components/payload-compare-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getSubjectHistory } from "@/lib/queries";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ expedienteKey: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}

export default async function ExpedienteDetailPage({ params, searchParams }: Props) {
  const [{ expedienteKey }, sp] = await Promise.all([params, searchParams]);
  const decodedKey = decodeURIComponent(expedienteKey);
  const page = sp.page ? Number(sp.page) : 1;
  const history = await getSubjectHistory("expediente", decodedKey, {
    page,
    pageSize: 25,
  });

  if (history.subjects.length === 0) {
    notFound();
  }

  const batchIds = Array.from(new Set(history.subjects.map((subject) => subject.batch_id).filter(Boolean))) as string[];

  return (
    <>
      <Header title={`Expediente ${decodedKey}`} description="Historial completo del sujeto expediente">
        <AutoRefresh />
        <Link href="/dashboard/expedientes">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
            Volver a Búsqueda
          </Button>
        </Link>
      </Header>

      <div className="space-y-6">
        <Card className="animate-slide-up border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Correlación</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-1.5">
              <RelationChip label="ocurrencias" value={history.subjects.length} />
              <RelationChip label="entradas" value={history.entries.total} />
              <RelationChip label="batches" value={batchIds.length} tone="warning" />
            </div>
            <div className="flex flex-wrap gap-1.5">
              {batchIds.map((batchId) => (
                <RelationChip key={batchId} label="batch" value={batchId} href={`/dashboard/batches/${encodeURIComponent(batchId)}`} tone="warning" />
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="animate-slide-up" style={{ animationDelay: "0ms" }}>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FolderOpen className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              Ocurrencias ({history.subjects.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SubjectsTable subjects={history.subjects} />
          </CardContent>
        </Card>

        <Card className="animate-slide-up" style={{ animationDelay: "100ms" }}>
          <CardHeader>
            <CardTitle className="text-base">Etapas</CardTitle>
          </CardHeader>
          <CardContent>
            <StageTree stages={history.stages} />
          </CardContent>
        </Card>

        <Card className="animate-slide-up" style={{ animationDelay: "200ms" }}>
          <CardHeader>
            <CardTitle className="text-base">Entradas ({history.entries.total})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <PayloadComparePanel entries={history.entries.rows} />
            <EntriesTable entries={history.entries.rows} />
            <Pagination page={history.entries.page} totalPages={history.entries.totalPages} total={history.entries.total} />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
