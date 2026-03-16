import type { ReactNode } from "react";
import type { StageRunRow } from "@/lib/queries";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/utils";
import { RelationChip } from "@/components/relation-chip";
import { AttrsPanel } from "@/components/attrs-panel";

interface StageTreeProps {
  stages: StageRunRow[];
}

function renderStageTree(stages: StageRunRow[], parentStageId: string | null = null, depth = 0): ReactNode {
  const children = stages.filter((stage) => (stage.parent_stage_id ?? null) === parentStageId);

  return children.map((stage, index) => {
    const maxDuration = Math.max(...stages.map((s) => s.duration_ms ?? 0), 1);
    const widthPercent = stage.duration_ms != null ? Math.max(8, (stage.duration_ms / maxDuration) * 100) : 0;
    const isError = stage.stage_status === "error" || stage.stage_status === "failed";
    const isLast = index === children.length - 1;

    return (
      <div key={stage.stage_id} className="relative">
        {/* Connector line */}
        {depth > 0 && (
          <div
            className="absolute top-0 w-px bg-border/50"
            style={{ left: `${(depth - 1) * 24 + 11}px`, height: isLast ? "20px" : "100%" }}
            aria-hidden="true"
          />
        )}
        {depth > 0 && (
          <div
            className="absolute top-5 h-px bg-border/50"
            style={{ left: `${(depth - 1) * 24 + 11}px`, width: "13px" }}
            aria-hidden="true"
          />
        )}

        <div
          className={`rounded-xl border bg-card/80 p-3.5 hover:bg-card transition-colors duration-150 ${isError ? "border-l-2 border-l-destructive/50" : "border-border/60"}`}
          style={{ marginLeft: `${depth * 24}px` }}
        >
          <div className="flex flex-wrap items-center gap-2">
            <code className="rounded-md bg-muted px-2 py-1 text-xs font-mono font-medium">{stage.stage_key}</code>
            <StatusBadge status={stage.stage_status} />
            {stage.subject_key && <span className="text-xs font-mono text-muted-foreground">{stage.subject_key}</span>}
            {stage.duration_ms != null && (
              <span className="text-xs font-mono text-muted-foreground tabular-nums">
                {stage.duration_ms.toLocaleString()} ms
              </span>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <RelationChip label="batch" value={stage.batch_id} href={stage.batch_id ? `/dashboard/batches/${encodeURIComponent(stage.batch_id)}` : null} tone="warning" />
            <RelationChip label="dep" value={stage.dependency} tone="info" />
            <RelationChip label="ctx" value={stage.context_result} tone="success" />
            <RelationChip label="try" value={stage.attempt_count} />
          </div>

          {/* Duration bar */}
          {stage.duration_ms != null && widthPercent > 0 && (
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-muted/70">
              <div
                className={`h-full rounded-full transition-all duration-500 ${isError ? "bg-gradient-to-r from-rose-500 to-rose-400" : "bg-gradient-to-r from-primary/70 to-primary/50"}`}
                style={{ width: `${widthPercent}%` }}
              />
            </div>
          )}

          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
            <span className="tabular-nums">{formatDate(stage.started_at)}</span>
            {stage.error_message && <span className="text-rose-400 truncate max-w-xs">{stage.error_message}</span>}
          </div>
          <div className="mt-2">
            <AttrsPanel attrs={stage.attrs} />
          </div>
        </div>

        <div className="mt-2 space-y-2">
          {renderStageTree(stages, stage.stage_id, depth + 1)}
        </div>
      </div>
    );
  });
}

export function StageTree({ stages }: StageTreeProps) {
  if (stages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
        <p className="text-sm font-medium">No se registraron etapas</p>
        <p className="text-xs text-muted-foreground/60 mt-1">Las etapas aparecerán cuando se procesen operaciones</p>
      </div>
    );
  }

  return <div className="space-y-2">{renderStageTree(stages)}</div>;
}
