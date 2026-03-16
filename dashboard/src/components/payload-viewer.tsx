"use client";

import { Check, Copy, Download, Eye, FileJson, LoaderCircle } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

interface PayloadViewerProps {
  payloadJson: Record<string, unknown> | unknown[] | null;
  payloadText?: string | null;
  payloadHash?: string | null;
  payloadBytes?: number | null;
  payloadTruncated?: boolean;
  sanitized?: boolean;
  route?: string | null;
  stageKey?: string | null;
  rawPayloadId?: number | null;
  rawPayloadAvailable?: boolean;
  rawPayloadTruncated?: boolean;
}

function isMeaningfulValue(value: unknown): boolean {
  if (value == null) {
    return false;
  }
  if (typeof value === "string") {
    return value.trim().length > 0;
  }
  if (Array.isArray(value)) {
    return value.some(isMeaningfulValue);
  }
  if (typeof value === "object") {
    return Object.values(value as Record<string, unknown>).some(isMeaningfulValue);
  }
  return true;
}

interface RevealedPayload {
  metadata: {
    content_kind: string;
    payload_hash: string;
    raw_bytes: number;
    truncated: boolean;
  };
  isText: boolean;
  text: string | null;
  base64: string | null;
}

export function PayloadViewer({
  payloadJson,
  payloadText,
  payloadHash,
  payloadBytes,
  payloadTruncated,
  sanitized,
  route,
  stageKey,
  rawPayloadId,
  rawPayloadAvailable,
  rawPayloadTruncated,
}: PayloadViewerProps) {
  const [copied, setCopied] = useState(false);
  const [revealed, setRevealed] = useState<RevealedPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const hasMeaningfulJson = payloadJson ? isMeaningfulValue(payloadJson) : false;
  const isSensitivePayload =
    route?.includes("firma") ||
    route?.includes("validar") ||
    stageKey?.startsWith("pdf.sign") ||
    stageKey?.startsWith("dss.validate") ||
    stageKey?.startsWith("jades.sign");

  const normalizedContent = useMemo(() => {
    if (isSensitivePayload) {
      return JSON.stringify(
        {
          redacted: true,
          payloadBytes: payloadBytes ?? null,
          payloadHash: payloadHash ?? null,
          payloadTruncated: payloadTruncated ?? false,
          rawPayloadAvailable: rawPayloadAvailable ?? false,
        },
        null,
        2,
      );
    }
    if (hasMeaningfulJson) {
      return JSON.stringify(payloadJson, null, 2);
    }
    return payloadText ?? "";
  }, [hasMeaningfulJson, isSensitivePayload, payloadBytes, payloadHash, payloadJson, payloadText, payloadTruncated, rawPayloadAvailable]);

  if (!hasMeaningfulJson && payloadText?.trim() === "" && !payloadHash && !payloadBytes) {
    return <span className="text-muted-foreground/30">—</span>;
  }

  if (!hasMeaningfulJson && !payloadText && !payloadHash && !payloadBytes) {
    return <span className="text-muted-foreground/30">—</span>;
  }

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(revealed?.text ?? revealed?.base64 ?? normalizedContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard may be unavailable.
    }
  }, [normalizedContent, revealed]);

  const revealPayload = useCallback(async () => {
    if (!rawPayloadId || !rawPayloadAvailable) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`/api/payload-vault/${rawPayloadId}/reveal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "payload-viewer" }),
      });
      if (!response.ok) {
        throw new Error("reveal_failed");
      }
      const data = (await response.json()) as RevealedPayload;
      setRevealed(data);
    } finally {
      setLoading(false);
    }
  }, [rawPayloadAvailable, rawPayloadId]);

  const downloadPayload = useCallback(() => {
    if (!revealed) {
      return;
    }

    const blob = revealed.isText
      ? new Blob([revealed.text ?? ""], { type: revealed.metadata.content_kind || "text/plain;charset=utf-8" })
      : new Blob([Uint8Array.from(atob(revealed.base64 ?? ""), (char) => char.charCodeAt(0))], { type: revealed.metadata.content_kind || "application/octet-stream" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `payload-${rawPayloadId ?? "raw"}`;
    anchor.click();
    URL.revokeObjectURL(url);
  }, [rawPayloadId, revealed]);

  return (
    <details className="group rounded-lg border border-border/50 bg-muted/20 p-2 transition-colors hover:border-border/70">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-xs text-muted-foreground select-none">
        <FileJson className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span className="font-medium">Payload</span>
        {payloadBytes != null && <span className="tabular-nums">{payloadBytes.toLocaleString()} bytes</span>}
        {sanitized && <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400">sanitized</span>}
        {payloadTruncated && <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400">truncated</span>}
        {rawPayloadAvailable && <span className="rounded-full bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-400">vault</span>}
      </summary>
      <div className="mt-2 space-y-2 animate-slide-down">
        <div className="relative">
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-background/80 border border-border/30 p-3 text-[11px] leading-5 text-foreground/90 font-mono">
            {revealed
              ? revealed.isText
                ? revealed.text
                : JSON.stringify(
                    {
                      binary: true,
                      base64Length: revealed.base64?.length ?? 0,
                      contentKind: revealed.metadata.content_kind,
                    },
                    null,
                    2,
                  )
              : normalizedContent}
          </pre>
          <div className="absolute right-2 top-2 flex items-center gap-1">
            {rawPayloadAvailable && !revealed && (
              <button
                onClick={revealPayload}
                className="rounded-md border border-border/40 bg-muted/80 p-1.5 text-muted-foreground transition-all duration-150 hover:bg-muted hover:text-foreground"
                title="Revelar payload crudo"
                disabled={loading}
              >
                {loading ? <LoaderCircle className="h-3 w-3 animate-spin" /> : <Eye className="h-3 w-3" />}
              </button>
            )}
            {revealed && (
              <button
                onClick={downloadPayload}
                className="rounded-md border border-border/40 bg-muted/80 p-1.5 text-muted-foreground transition-all duration-150 hover:bg-muted hover:text-foreground"
                title="Descargar payload"
              >
                <Download className="h-3 w-3" />
              </button>
            )}
            <button
              onClick={handleCopy}
              className="rounded-md border border-border/40 bg-muted/80 p-1.5 text-muted-foreground transition-all duration-150 hover:bg-muted hover:text-foreground"
              title="Copiar al portapapeles"
            >
              {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
            </button>
          </div>
        </div>
        {payloadHash && (
          <div className="space-y-1">
            <div className="font-mono text-[10px] text-muted-foreground/60 break-all">sha256: {payloadHash}</div>
            {rawPayloadId != null && (
              <div className="font-mono text-[10px] text-muted-foreground/60">
                vault #{rawPayloadId}
                {rawPayloadTruncated ? " (truncated)" : ""}
              </div>
            )}
          </div>
        )}
      </div>
    </details>
  );
}
