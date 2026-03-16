import crypto from "crypto";
import { gunzipSync } from "zlib";
import { query } from "@/lib/db";
import type { PayloadCompareResult, PayloadVaultMetadata } from "@/lib/queries";

function getVaultKey(): Buffer {
  const raw = process.env.OBS_PAYLOAD_VAULT_KEY;
  if (!raw) {
    throw new Error("payload_vault_disabled");
  }
  const decoded = Buffer.from(raw, "base64");
  if (decoded.length !== 32) {
    throw new Error("payload_vault_key_invalid");
  }
  return decoded;
}

function decryptPayload(ciphertext: Buffer, nonce: Buffer): Buffer {
  const key = getVaultKey();
  const tag = ciphertext.subarray(ciphertext.length - 16);
  const body = ciphertext.subarray(0, ciphertext.length - 16);
  const decipher = crypto.createDecipheriv("aes-256-gcm", key, nonce);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(body), decipher.final()]);
}

function decodeBinaryPayload(buffer: Buffer, contentKind: string) {
  const isTextual =
    contentKind.includes("json") ||
    contentKind.includes("text") ||
    contentKind.includes("request") ||
    contentKind.includes("response");

  if (!isTextual) {
    return { isText: false, text: null, base64: buffer.toString("base64") };
  }

  try {
    return { isText: true, text: buffer.toString("utf-8"), base64: null };
  } catch {
    return { isText: false, text: null, base64: buffer.toString("base64") };
  }
}

export async function revealPayloadVaultEntry(vaultId: number): Promise<{
  metadata: PayloadVaultMetadata;
  isText: boolean;
  text: string | null;
  base64: string | null;
}> {
  const res = await query<PayloadVaultMetadata & { ciphertext: Buffer; nonce: Buffer }>(
    `
    SELECT
      vault_id,
      operation_id::text,
      subject_id::text,
      stage_id::text,
      entry_kind,
      route,
      stage_key,
      payload_hash,
      content_kind,
      ciphertext,
      nonce,
      algorithm,
      compression,
      raw_bytes,
      stored_bytes,
      truncated,
      created_at,
      expires_at,
      attrs
    FROM observability.payload_vault
    WHERE vault_id = $1
    `,
    [vaultId],
  );
  const row = res.rows[0];
  if (!row) {
    throw new Error("not_found");
  }

  const decrypted = decryptPayload(row.ciphertext, row.nonce);
  const payload = row.compression === "gzip" ? gunzipSync(decrypted) : decrypted;
  const decoded = decodeBinaryPayload(payload, row.content_kind);

  const { ciphertext: _ciphertext, nonce: _nonce, ...metadata } = row;
  return {
    metadata,
    ...decoded,
  };
}

export function buildPayloadCompare(left: Awaited<ReturnType<typeof revealPayloadVaultEntry>>, right: Awaited<ReturnType<typeof revealPayloadVaultEntry>>): PayloadCompareResult {
  const textDiff =
    left.isText && right.isText && left.text !== null && right.text !== null
      ? [left.text, right.text].join("\n\n===== COMPARE =====\n\n")
      : null;

  return {
    left: left.metadata,
    right: right.metadata,
    same_hash: left.metadata.payload_hash === right.metadata.payload_hash,
    same_size: left.metadata.raw_bytes === right.metadata.raw_bytes,
    same_content_kind: left.metadata.content_kind === right.metadata.content_kind,
    text_diff: textDiff,
  };
}
