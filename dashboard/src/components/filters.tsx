"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search, X, Filter, ChevronDown, ChevronUp } from "lucide-react";
import { useCallback, useState, useMemo } from "react";
import { cn } from "@/lib/utils";

interface FiltersProps {
  stageKeys?: string[];
  operationKeys?: string[];
  loggerNames?: string[];
  errorCodes?: string[];
  dependencies?: string[];
  statuses?: string[];
  entryKinds?: string[];
  contextResults?: string[];
  showDocumentSearch?: boolean;
  showExpedienteSearch?: boolean;
  showBatchSearch?: boolean;
  showPayloadHashSearch?: boolean;
  showStageSelect?: boolean;
  showOperationKeySelect?: boolean;
  showLoggerNameSelect?: boolean;
  showErrorCodeSelect?: boolean;
  showDependencySelect?: boolean;
  showStatusSelect?: boolean;
  showEntryKindSelect?: boolean;
  showLogLevelSelect?: boolean;
  showContextResultSelect?: boolean;
  showRetryableSelect?: boolean;
  showSortSelect?: boolean;
}

const LOG_LEVELS = ["debug", "info", "warning", "error"];
const SORT_OPTIONS = ["desc", "asc"];
const RETRYABLE_OPTIONS = ["true", "false"];

export function Filters({
  stageKeys = [],
  operationKeys = [],
  loggerNames = [],
  errorCodes = [],
  dependencies = [],
  statuses = [],
  entryKinds = [],
  contextResults = [],
  showDocumentSearch,
  showExpedienteSearch,
  showBatchSearch,
  showPayloadHashSearch,
  showStageSelect,
  showOperationKeySelect,
  showLoggerNameSelect,
  showErrorCodeSelect,
  showDependencySelect,
  showStatusSelect,
  showEntryKindSelect,
  showLogLevelSelect,
  showContextResultSelect,
  showRetryableSelect,
  showSortSelect,
}: FiltersProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [docId, setDocId] = useState(searchParams.get("document_id") ?? "");
  const [expKey, setExpKey] = useState(searchParams.get("expediente_key") ?? "");
  const [batchId, setBatchId] = useState(searchParams.get("batch_id") ?? "");
  const [payloadHash, setPayloadHash] = useState(searchParams.get("payload_hash") ?? "");
  const [attemptCount, setAttemptCount] = useState(searchParams.get("attempt_count") ?? "");
  const [isExpanded, setIsExpanded] = useState(true);

  const push = useCallback(
    (overrides: Record<string, string | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("page");
      for (const [key, value] of Object.entries(overrides)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      router.push(`${pathname}?${params.toString()}`);
    },
    [pathname, router, searchParams],
  );

  const activeStageKey = searchParams.get("stage_key") ?? "";
  const activeOperationKey = searchParams.get("operation_key") ?? "";
  const activeLoggerName = searchParams.get("logger_name") ?? "";
  const activeErrorCode = searchParams.get("error_code") ?? "";
  const activeDependency = searchParams.get("dependency") ?? "";
  const activeStatus = searchParams.get("status") ?? "";
  const activeEntryKind = searchParams.get("entry_kind") ?? "";
  const activeLogLevel = searchParams.get("log_level") ?? "";
  const activeContextResult = searchParams.get("context_result") ?? "";
  const activeRetryable = searchParams.get("retryable") ?? "";
  const activeSort = searchParams.get("sort") ?? "";
  const activeFrom = searchParams.get("from") ?? "";
  const activeTo = searchParams.get("to") ?? "";

  const activeFilterCount = useMemo(() => {
    let count = 0;
    for (const value of [
      docId,
      expKey,
      batchId,
      payloadHash,
      attemptCount,
      activeStageKey,
      activeOperationKey,
      activeLoggerName,
      activeErrorCode,
      activeDependency,
      activeStatus,
      activeEntryKind,
      activeLogLevel,
      activeContextResult,
      activeRetryable,
      activeSort,
      activeFrom,
      activeTo,
    ]) {
      if (value) count++;
    }
    return count;
  }, [activeContextResult, activeDependency, activeEntryKind, activeErrorCode, activeFrom, activeLogLevel, activeLoggerName, activeOperationKey, activeRetryable, activeSort, activeStageKey, activeStatus, activeTo, attemptCount, batchId, docId, expKey, payloadHash]);

  const hasFilters = activeFilterCount > 0;

  return (
    <div className="pb-5 animate-slide-up">
      <button
        onClick={() => setIsExpanded((e) => !e)}
        className="flex items-center gap-2 mb-3 text-xs text-muted-foreground hover:text-foreground transition-colors duration-150 group"
      >
        <Filter className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="font-medium">Filtros</span>
        {activeFilterCount > 0 && (
          <Badge variant="info" className="text-[10px] py-0 px-1.5 tabular-nums">
            {activeFilterCount}
          </Badge>
        )}
        {isExpanded ? <ChevronUp className="h-3 w-3" aria-hidden="true" /> : <ChevronDown className="h-3 w-3" aria-hidden="true" />}
      </button>

      <div className={cn("overflow-hidden transition-all duration-250", isExpanded ? "max-h-[900px] opacity-100" : "max-h-0 opacity-0")}>
        <div className="rounded-xl border border-border/60 bg-card/50 p-4 space-y-4">
          {(showDocumentSearch || showExpedienteSearch || showBatchSearch || showPayloadHashSearch) && (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {showDocumentSearch && (
                <SearchField label="ID Documento" value={docId} setValue={setDocId} onApply={() => push({ document_id: docId || undefined })} />
              )}
              {showExpedienteSearch && (
                <SearchField label="Expediente" value={expKey} setValue={setExpKey} onApply={() => push({ expediente_key: expKey || undefined })} />
              )}
              {showBatchSearch && (
                <SearchField label="Batch" value={batchId} setValue={setBatchId} onApply={() => push({ batch_id: batchId || undefined })} />
              )}
              {showPayloadHashSearch && (
                <SearchField label="Payload Hash" value={payloadHash} setValue={setPayloadHash} onApply={() => push({ payload_hash: payloadHash || undefined })} />
              )}
            </div>
          )}

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            {showOperationKeySelect && operationKeys.length > 0 && (
              <SelectFilter id="filter-operation-key" label="Operación" value={activeOperationKey} options={operationKeys} onChange={(value) => push({ operation_key: value || undefined })} />
            )}
            {showStageSelect && stageKeys.length > 0 && (
              <SelectFilter id="filter-stage" label="Etapa" value={activeStageKey} options={stageKeys} onChange={(value) => push({ stage_key: value || undefined })} />
            )}
            {showLoggerNameSelect && loggerNames.length > 0 && (
              <SelectFilter id="filter-logger" label="Logger" value={activeLoggerName} options={loggerNames} onChange={(value) => push({ logger_name: value || undefined })} />
            )}
            {showErrorCodeSelect && errorCodes.length > 0 && (
              <SelectFilter id="filter-error-code" label="Error Code" value={activeErrorCode} options={errorCodes} onChange={(value) => push({ error_code: value || undefined })} />
            )}
            {showDependencySelect && dependencies.length > 0 && (
              <SelectFilter id="filter-dependency" label="Dependencia" value={activeDependency} options={dependencies} onChange={(value) => push({ dependency: value || undefined })} />
            )}
            {showStatusSelect && statuses.length > 0 && (
              <SelectFilter id="filter-status" label="Estado" value={activeStatus} options={statuses} onChange={(value) => push({ status: value || undefined })} />
            )}
            {showEntryKindSelect && entryKinds.length > 0 && (
              <SelectFilter id="filter-kind" label="Tipo" value={activeEntryKind} options={entryKinds} onChange={(value) => push({ entry_kind: value || undefined })} />
            )}
            {showLogLevelSelect && (
              <SelectFilter id="filter-level" label="Nivel" value={activeLogLevel} options={LOG_LEVELS} onChange={(value) => push({ log_level: value || undefined })} />
            )}
            {showContextResultSelect && contextResults.length > 0 && (
              <SelectFilter id="filter-context" label="Contexto" value={activeContextResult} options={contextResults} onChange={(value) => push({ context_result: value || undefined })} />
            )}
            {showRetryableSelect && (
              <SelectFilter id="filter-retryable" label="Retryable" value={activeRetryable} options={RETRYABLE_OPTIONS} onChange={(value) => push({ retryable: value || undefined })} />
            )}
            {showSortSelect && (
              <SelectFilter id="filter-sort" label="Orden" value={activeSort || "desc"} options={SORT_OPTIONS} onChange={(value) => push({ sort: value || undefined })} />
            )}
            <div className="w-full">
              <label htmlFor="filter-attempt-count" className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Attempt Count
              </label>
              <Input
                id="filter-attempt-count"
                placeholder="Exacto"
                value={attemptCount}
                onChange={(e) => setAttemptCount(e.target.value)}
                onBlur={() => push({ attempt_count: attemptCount || undefined })}
                className="h-9 w-full text-sm"
              />
            </div>
            <div className="w-full">
              <label htmlFor="filter-from" className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Desde
              </label>
              <Input id="filter-from" type="date" value={activeFrom} onChange={(e) => push({ from: e.target.value || undefined })} className="h-9 w-full text-sm" />
            </div>
            <div className="w-full">
              <label htmlFor="filter-to" className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Hasta
              </label>
              <Input id="filter-to" type="date" value={activeTo} onChange={(e) => push({ to: e.target.value || undefined })} className="h-9 w-full text-sm" />
            </div>
          </div>

          {hasFilters && (
            <Button
              variant="outline"
              className="h-9 gap-1.5"
              onClick={() => {
                setDocId("");
                setExpKey("");
                setBatchId("");
                setPayloadHash("");
                setAttemptCount("");
                router.push(pathname);
              }}
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
              Limpiar
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function SearchField({
  label,
  value,
  setValue,
  onApply,
}: {
  label: string;
  value: string;
  setValue: (value: string) => void;
  onApply: () => void;
}) {
  return (
    <div className="w-full">
      <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</label>
      <div className="flex items-center gap-1.5">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/40" aria-hidden="true" />
          <Input
            placeholder="Buscar..."
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="h-9 w-full pl-8 font-mono text-sm"
            onKeyDown={(e) => {
              if (e.key === "Enter") onApply();
            }}
          />
        </div>
        <Button size="sm" variant="secondary" className="h-9 px-3" onClick={onApply}>
          <Search className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}

function SelectFilter({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="w-full">
      <label htmlFor={id} className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </label>
      <div className="relative">
        <Filter className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/40" aria-hidden="true" />
        <select
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            "h-9 w-full cursor-pointer appearance-none rounded-md border border-input bg-background pl-8 pr-8 text-sm transition-all duration-150",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 focus-visible:border-primary/50",
            "select-styled",
            value ? "text-foreground" : "text-muted-foreground",
          )}
        >
          <option value="">Todos</option>
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
