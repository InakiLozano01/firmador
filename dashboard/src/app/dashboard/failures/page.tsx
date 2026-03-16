import { Suspense } from "react";
import { AlertTriangle } from "lucide-react";
import { Header } from "@/components/header";
import { AutoRefresh } from "@/components/auto-refresh";
import { Filters } from "@/components/filters";
import { EntriesTable } from "@/components/entries-table";
import { Pagination } from "@/components/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { getEntries, getDistinctContextResults, getDistinctDependencies, getDistinctErrorCodes, getDistinctLoggerNames, getDistinctOperationKeys, getDistinctStageKeys } from "@/lib/queries";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | undefined>>;
}

async function FailuresContent({ searchParams }: Props) {
  const params = await searchParams;
  const [entriesPage, operationKeys, stageKeys, loggerNames, errorCodes, dependencies, contextResults] = await Promise.all([
    getEntries({
      document_id: params.document_id,
      expediente_key: params.expediente_key,
      batch_id: params.batch_id,
      stage_key: params.stage_key,
      operation_key: params.operation_key,
      logger_name: params.logger_name,
      error_code: params.error_code,
      dependency: params.dependency,
      context_result: params.context_result,
      retryable: params.retryable === "true" ? true : params.retryable === "false" ? false : undefined,
      payload_hash: params.payload_hash,
      attempt_count: params.attempt_count ? Number(params.attempt_count) : undefined,
      from: params.from,
      to: params.to,
      log_level: "error", // Force only errors here
      sortDirection: "desc",
      page: params.page ? Number(params.page) : 1,
      pageSize: 25,
    }),
    getDistinctOperationKeys(),
    getDistinctStageKeys(),
    getDistinctLoggerNames(),
    getDistinctErrorCodes(),
    getDistinctDependencies(),
    getDistinctContextResults(),
  ]);

  return (
    <>
      <Filters
        operationKeys={operationKeys}
        stageKeys={stageKeys}
        loggerNames={loggerNames}
        errorCodes={errorCodes}
        dependencies={dependencies}
        contextResults={contextResults}
        showDocumentSearch
        showExpedienteSearch
        showBatchSearch
        showPayloadHashSearch
        showOperationKeySelect
        showStageSelect
        showLoggerNameSelect
        showErrorCodeSelect
        showDependencySelect
        showContextResultSelect
        showRetryableSelect
      />

      {entriesPage.rows.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground animate-fade-in">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/60 border border-border/50">
            <AlertTriangle className="h-6 w-6 text-muted-foreground/40" aria-hidden="true" />
          </div>
          <p className="text-sm font-medium">No se encontraron errores</p>
          <p className="text-xs text-muted-foreground/60 mt-1">Con los filtros actuales o en el sistema</p>
        </div>
      ) : (
        <>
          <div className="mb-4 rounded-lg bg-rose-500/10 border border-rose-500/20 px-4 py-3 text-sm text-rose-500 flex items-center gap-2 animate-fade-in">
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
            Mostrando eventos con nivel <strong>error</strong> o tipo <strong>error</strong>.
          </div>
          <EntriesTable entries={entriesPage.rows} />
          <Pagination page={entriesPage.page} totalPages={entriesPage.totalPages} total={entriesPage.total} />
        </>
      )}
    </>
  );
}

export default function FailuresPage(props: Props) {
  return (
    <>
      <Header title="Errores" description="Búsqueda global de errores, fallos y excepciones">
        <AutoRefresh />
      </Header>
      <Suspense fallback={<Skeleton className="h-96 rounded-lg" />}>
        <FailuresContent searchParams={props.searchParams} />
      </Suspense>
    </>
  );
}
