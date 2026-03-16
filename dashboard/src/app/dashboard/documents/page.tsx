import { Suspense } from "react";
import { FileText } from "lucide-react";
import { Header } from "@/components/header";
import { AutoRefresh } from "@/components/auto-refresh";
import { Filters } from "@/components/filters";
import { SubjectsTable } from "@/components/subjects-table";
import { Pagination } from "@/components/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { getSubjects } from "@/lib/queries";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | undefined>>;
}

async function DocumentsContent({ searchParams }: Props) {
  const params = await searchParams;
  const page = await getSubjects({
    subject_key: params.document_id,
    subjectType: "document",
    status: params.status,
    from: params.from,
    to: params.to,
    page: params.page ? Number(params.page) : 1,
    pageSize: 25,
  });

  return (
    <>
      <Filters
        statuses={["running", "success", "error", "failed"]}
        showDocumentSearch
        showStatusSelect
      />

      {page.rows.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground animate-fade-in">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/60 border border-border/50">
            <FileText className="h-6 w-6 text-muted-foreground/40" aria-hidden="true" />
          </div>
          <p className="text-sm font-medium">No se encontraron documentos</p>
          <p className="text-xs text-muted-foreground/60 mt-1">Ingresá un ID o ajustá los filtros de búsqueda</p>
        </div>
      ) : (
        <>
          <SubjectsTable subjects={page.rows} />
          <Pagination page={page.page} totalPages={page.totalPages} total={page.total} />
        </>
      )}
    </>
  );
}

export default function DocumentsPage(props: Props) {
  return (
    <>
      <Header title="Documentos" description="Búsqueda de documentos y su estado en el sistema">
        <AutoRefresh />
      </Header>
      <Suspense fallback={<Skeleton className="h-96 rounded-lg" />}>
        <DocumentsContent searchParams={props.searchParams} />
      </Suspense>
    </>
  );
}
