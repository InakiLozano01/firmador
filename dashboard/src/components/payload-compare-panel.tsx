"use client";

import { useMemo, useState } from "react";
import type { EntryRow, PayloadCompareResult } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { RelationChip } from "@/components/relation-chip";

interface PayloadComparePanelProps {
  entries: EntryRow[];
}

export function PayloadComparePanel({ entries }: PayloadComparePanelProps) {
  const candidates = useMemo(
    () =>
      entries.filter((entry) => entry.raw_payload_available && entry.raw_payload_id != null).map((entry) => ({
        id: String(entry.raw_payload_id),
        label: `${entry.stage_key ?? entry.entry_kind} · ${entry.occurred_at}`,
      })),
    [entries],
  );
  const [leftVaultId, setLeftVaultId] = useState(candidates[0]?.id ?? "");
  const [rightVaultId, setRightVaultId] = useState(candidates[1]?.id ?? candidates[0]?.id ?? "");
  const [compare, setCompare] = useState<PayloadCompareResult | null>(null);
  const [loading, setLoading] = useState(false);

  if (candidates.length < 2) {
    return null;
  }

  async function handleCompare() {
    setLoading(true);
    try {
      const response = await fetch("/api/payload-vault/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          leftVaultId: Number(leftVaultId),
          rightVaultId: Number(rightVaultId),
          reason: "dashboard-compare-panel",
        }),
      });
      if (!response.ok) {
        throw new Error("compare_failed");
      }
      setCompare((await response.json()) as PayloadCompareResult);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl border border-border/60 bg-background/40 p-4 space-y-3">
      <div className="text-sm font-semibold">Comparar payloads del vault</div>
      <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
        <select value={leftVaultId} onChange={(e) => setLeftVaultId(e.target.value)} className="h-10 rounded-lg border border-input bg-background px-3 text-sm">
          {candidates.map((candidate) => (
            <option key={`left-${candidate.id}`} value={candidate.id}>
              {candidate.label}
            </option>
          ))}
        </select>
        <select value={rightVaultId} onChange={(e) => setRightVaultId(e.target.value)} className="h-10 rounded-lg border border-input bg-background px-3 text-sm">
          {candidates.map((candidate) => (
            <option key={`right-${candidate.id}`} value={candidate.id}>
              {candidate.label}
            </option>
          ))}
        </select>
        <Button onClick={handleCompare} disabled={loading || !leftVaultId || !rightVaultId}>
          {loading ? "Comparando..." : "Comparar"}
        </Button>
      </div>
      {compare && (
        <div className="space-y-3 rounded-2xl border border-border/60 bg-card/70 p-4">
          <div className="flex flex-wrap gap-1.5">
            <RelationChip label="same hash" value={compare.same_hash} tone={compare.same_hash ? "success" : "danger"} />
            <RelationChip label="same size" value={compare.same_size} tone={compare.same_size ? "success" : "warning"} />
            <RelationChip label="same kind" value={compare.same_content_kind} tone={compare.same_content_kind ? "success" : "warning"} />
          </div>
          {compare.text_diff && (
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border/40 bg-background/80 p-3 text-[11px] leading-5 font-mono">
              {compare.text_diff}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
