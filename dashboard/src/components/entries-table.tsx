import Link from "next/link";
import type { EntryRow } from "@/lib/queries";
import { PayloadViewer } from "@/components/payload-viewer";
import { StatusBadge } from "@/components/status-badge";
import { AttrsPanel } from "@/components/attrs-panel";
import { RelationChip } from "@/components/relation-chip";
import { formatDate } from "@/lib/utils";
import { Inbox } from "lucide-react";

interface EntriesTableProps {
  entries: EntryRow[];
}

const MESSAGE_PREVIEW_LIMIT = 280;

function MessagePreview({ message }: { message: string }) {
  if (message.length <= MESSAGE_PREVIEW_LIMIT) {
    return <div className="text-muted-foreground whitespace-pre-wrap break-words">{message}</div>;
  }

  const preview = `${message.slice(0, MESSAGE_PREVIEW_LIMIT).trimEnd()}...`;

  return (
    <details className="group rounded-lg border border-border/50 bg-background/50 p-2">
      <summary className="cursor-pointer list-none space-y-1 text-muted-foreground">
        <div className="whitespace-pre-wrap break-words">{preview}</div>
        <div className="text-[10px] font-semibold uppercase tracking-wider text-primary/80">
          Ver mensaje completo
        </div>
      </summary>
      <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-md border border-border/40 bg-background/80 p-2 text-[11px] leading-5 text-foreground/85 font-mono">
        {message}
      </pre>
    </details>
  );
}

function subjectHref(entry: EntryRow): string | null {
  if (entry.subject_type === "document" && entry.subject_key) {
    return `/dashboard/documents/${encodeURIComponent(entry.subject_key)}`;
  }
  if (entry.subject_type === "expediente" && entry.subject_key) {
    return `/dashboard/expedientes/${encodeURIComponent(entry.subject_key)}`;
  }
  return null;
}

function entryChips(entry: EntryRow) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <RelationChip label="batch" value={entry.batch_id} href={entry.batch_id ? `/dashboard/batches/${encodeURIComponent(entry.batch_id)}` : null} tone="warning" />
      <RelationChip label="dep" value={entry.dependency} tone="info" />
      <RelationChip label="ctx" value={entry.context_result} tone="success" />
      <RelationChip label="try" value={entry.attempt_count} />
      <RelationChip label="retry" value={entry.retryable} tone={entry.retryable ? "success" : "default"} />
      <RelationChip label="code" value={entry.error_code} tone="danger" />
      <RelationChip label="hash" value={entry.payload_hash?.slice(0, 12)} href={entry.payload_hash ? `/dashboard/failures?payload_hash=${encodeURIComponent(entry.payload_hash)}` : null} />
    </div>
  );
}

export function EntriesTable({ entries }: EntriesTableProps) {
  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground animate-fade-in">
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/60 border border-border/50">
          <Inbox className="h-6 w-6 text-muted-foreground/40" aria-hidden="true" />
        </div>
        <p className="text-sm font-medium">No se encontraron entradas</p>
        <p className="text-xs text-muted-foreground/60 mt-1">Ajustá los filtros o esperá a que se generen nuevos eventos</p>
      </div>
    );
  }

  return (
    <>
      <div className="hidden md:block overflow-x-auto rounded-lg border border-border bg-card animate-slide-up">
        <table className="w-full text-sm table-striped">
          <thead>
            <tr className="border-b bg-muted/40">
              <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Fecha</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Evento</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Relaciones</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Payload</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Operación</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {entries.map((entry, index) => {
              const href = subjectHref(entry);
              const isError = entry.entry_kind === "error" || entry.log_level === "error";

              return (
                <tr
                  key={`${entry.occurred_at}-${entry.entry_id}`}
                  className={`align-top hover:bg-muted/40 transition-colors stagger-row ${isError ? "border-l-2 border-l-destructive/50" : ""}`}
                  style={{ animationDelay: `${index * 20}ms` }}
                >
                  <td className="px-4 py-2.5 whitespace-nowrap text-xs text-muted-foreground tabular-nums">
                    {formatDate(entry.occurred_at)}
                  </td>
                  <td className="px-4 py-2.5 text-xs max-w-md">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono">{entry.entry_kind}</code>
                        {entry.log_level ? <StatusBadge status={entry.log_level === "error" ? "error" : entry.log_level} /> : null}
                        {entry.stage_status ? <StatusBadge status={entry.stage_status} /> : null}
                      </div>
                      <div className="font-medium">{entry.title ?? "—"}</div>
                      {entry.stage_key && <code className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-mono">{entry.stage_key}</code>}
                      {entry.logger_name && <div className="font-mono text-[10px] text-muted-foreground/70">{entry.logger_name}</div>}
                      {entry.message && <MessagePreview message={entry.message} />}
                      {entry.error_class && <div className="font-mono text-[11px] text-rose-400">{entry.error_class}</div>}
                      <AttrsPanel attrs={entry.attrs} />
                    </div>
                  </td>
                  <td className="px-4 py-2.5 min-w-72 text-xs">
                    <div className="space-y-2">
                      {entryChips(entry)}
                      <div className="flex flex-wrap gap-1.5">
                        {href && entry.subject_key && (
                          <Link href={href} className="text-primary hover:underline underline-offset-2 font-mono">
                            {entry.subject_key}
                          </Link>
                        )}
                        {entry.error_code && (
                          <Link href={`/dashboard/failures?error_code=${encodeURIComponent(entry.error_code)}`} className="text-rose-300 hover:underline underline-offset-2 font-mono">
                            mismo error
                          </Link>
                        )}
                        {entry.dependency && (
                          <Link href={`/dashboard/dependencies?dependency=${encodeURIComponent(entry.dependency)}`} className="text-sky-300 hover:underline underline-offset-2 font-mono">
                            misma dependencia
                          </Link>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 min-w-80">
                    <PayloadViewer
                      payloadJson={entry.payload_json}
                      payloadText={entry.payload_text}
                      payloadHash={entry.payload_hash}
                      payloadBytes={entry.payload_bytes}
                      payloadTruncated={entry.payload_truncated}
                      sanitized={entry.sanitized}
                      route={entry.route}
                      stageKey={entry.stage_key}
                      rawPayloadId={entry.raw_payload_id}
                      rawPayloadAvailable={entry.raw_payload_available}
                      rawPayloadTruncated={entry.raw_payload_truncated}
                    />
                  </td>
                  <td className="px-4 py-2.5 text-xs font-mono">
                    <div className="space-y-1">
                      <Link href={`/dashboard/operations/${entry.operation_id}`} className="text-primary hover:underline underline-offset-2">
                        {entry.operation_key}
                      </Link>
                      {entry.batch_id && (
                        <Link href={`/dashboard/batches/${encodeURIComponent(entry.batch_id)}`} className="block text-amber-300 hover:underline underline-offset-2">
                          batch {entry.batch_id}
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="md:hidden space-y-3 animate-slide-up">
        {entries.map((entry, index) => {
          const href = subjectHref(entry);
          const isError = entry.entry_kind === "error" || entry.log_level === "error";

          return (
            <div
              key={`m-${entry.occurred_at}-${entry.entry_id}`}
              className={`rounded-xl border bg-card p-4 space-y-2.5 stagger-row ${isError ? "border-l-2 border-l-destructive/50" : "border-border"}`}
              style={{ animationDelay: `${index * 30}ms` }}
            >
              <div className="flex items-center justify-between gap-2">
                <code className="rounded-md bg-muted px-1.5 py-0.5 text-xs font-mono">{entry.entry_kind}</code>
                <span className="text-[10px] text-muted-foreground tabular-nums">{formatDate(entry.occurred_at)}</span>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {entry.log_level && <StatusBadge status={entry.log_level === "error" ? "error" : entry.log_level} />}
                {entry.stage_key && <code className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-mono">{entry.stage_key}</code>}
              </div>
              {entry.title && <div className="text-xs font-medium">{entry.title}</div>}
              {entry.message && <div className="text-xs"><MessagePreview message={entry.message} /></div>}
              {entryChips(entry)}
              <PayloadViewer
                payloadJson={entry.payload_json}
                payloadText={entry.payload_text}
                payloadHash={entry.payload_hash}
                payloadBytes={entry.payload_bytes}
                payloadTruncated={entry.payload_truncated}
                sanitized={entry.sanitized}
                route={entry.route}
                stageKey={entry.stage_key}
                rawPayloadId={entry.raw_payload_id}
                rawPayloadAvailable={entry.raw_payload_available}
                rawPayloadTruncated={entry.raw_payload_truncated}
              />
              <AttrsPanel attrs={entry.attrs} />
              <div className="flex items-center justify-between gap-2 pt-1 border-t border-border/40">
                {href && entry.subject_key ? (
                  <Link href={href} className="text-xs text-primary font-mono hover:underline underline-offset-2">
                    {entry.subject_key}
                  </Link>
                ) : (
                  <span />
                )}
                <Link href={`/dashboard/operations/${entry.operation_id}`} className="text-xs text-primary font-mono hover:underline underline-offset-2">
                  {entry.operation_key}
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
