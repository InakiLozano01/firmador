import Link from "next/link";
import type { OperationTimelineItem } from "@/lib/queries";
import { formatDate } from "@/lib/utils";
import { ArrowDownLeft, ArrowUpRight, CheckCircle2, CircleDot, FileText, OctagonAlert } from "lucide-react";
import { RelationChip } from "@/components/relation-chip";
import { AttrsPanel } from "@/components/attrs-panel";

interface OperationTimelineProps {
  items: OperationTimelineItem[];
}

function itemIcon(item: OperationTimelineItem) {
  if (item.timeline_kind === "stage_start") return CircleDot;
  if (item.timeline_kind === "stage_finish") return CheckCircle2;
  if (item.entry?.entry_kind === "http_request" || item.entry?.entry_kind === "external_request") return ArrowUpRight;
  if (item.entry?.entry_kind === "http_response" || item.entry?.entry_kind === "external_response") return ArrowDownLeft;
  if (item.entry?.entry_kind === "error" || item.entry?.log_level === "error") return OctagonAlert;
  return FileText;
}

export function OperationTimeline({ items }: OperationTimelineProps) {
  if (items.length === 0) {
    return <div className="py-10 text-sm text-muted-foreground">No hay eventos para esta operación.</div>;
  }

  return (
    <div className="space-y-3">
      {items.map((item, index) => {
        const Icon = itemIcon(item);
        const entry = item.entry;
        const stage = item.stage;
        const isError = entry?.entry_kind === "error" || entry?.log_level === "error" || stage?.stage_status === "error";

        return (
          <div
            key={item.timeline_id}
            className={`relative overflow-hidden rounded-2xl border bg-card/80 p-4 backdrop-blur-sm stagger-row ${isError ? "border-rose-500/20" : "border-border/60"}`}
            style={{ animationDelay: `${index * 20}ms` }}
          >
            <div className="absolute left-5 top-0 h-full w-px bg-gradient-to-b from-transparent via-border/60 to-transparent" aria-hidden="true" />
            <div className="relative flex gap-4">
              <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border ${isError ? "border-rose-500/30 bg-rose-500/10 text-rose-300" : "border-border/60 bg-muted/40 text-foreground/70"}`}>
                <Icon className="h-4 w-4" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold tracking-tight">{item.title}</div>
                    <div className="text-[11px] text-muted-foreground tabular-nums">{formatDate(item.occurred_at)}</div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <RelationChip label="kind" value={item.timeline_kind === "entry" ? entry?.entry_kind : item.timeline_kind} tone={isError ? "danger" : "default"} />
                    <RelationChip label="stage" value={item.stage_key} href={item.stage_id ? `/dashboard/operations/${item.entry?.operation_id ?? stage?.operation_id}` : null} tone="info" />
                    <RelationChip label="batch" value={entry?.batch_id ?? stage?.batch_id} href={entry?.batch_id ?? stage?.batch_id ? `/dashboard/batches/${encodeURIComponent(entry?.batch_id ?? stage?.batch_id ?? "")}` : null} tone="warning" />
                    <RelationChip label="dependency" value={entry?.dependency ?? stage?.dependency} tone="info" />
                    <RelationChip label="context" value={entry?.context_result ?? stage?.context_result} tone="success" />
                  </div>
                </div>

                {item.message && <div className="text-sm text-foreground/85 whitespace-pre-wrap break-words">{item.message}</div>}

                <div className="flex flex-wrap gap-1.5">
                  <RelationChip label="attempt" value={entry?.attempt_count ?? stage?.attempt_count} />
                  <RelationChip label="error" value={entry?.error_code} tone="danger" />
                  <RelationChip
                    label="subject"
                    value={entry?.subject_key ?? stage?.subject_key}
                    href={
                      entry?.subject_type === "document" || stage?.subject_type === "document"
                        ? `/dashboard/documents/${encodeURIComponent(entry?.subject_key ?? stage?.subject_key ?? "")}`
                        : entry?.subject_type === "expediente" || stage?.subject_type === "expediente"
                          ? `/dashboard/expedientes/${encodeURIComponent(entry?.subject_key ?? stage?.subject_key ?? "")}`
                          : null
                    }
                  />
                  {entry?.operation_id && (
                    <Link href={`/dashboard/operations/${entry.operation_id}`} className="text-[11px] font-mono text-primary hover:underline underline-offset-2">
                      {entry.operation_key}
                    </Link>
                  )}
                </div>

                <AttrsPanel attrs={entry?.attrs ?? stage?.attrs} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
