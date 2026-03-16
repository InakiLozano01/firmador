import { query } from "@/lib/db";
import type {
  EntryFilters,
  EntryRow,
  OperationTraceSummary,
  PaginatedResult,
  StageRunRow,
  SubjectSummary,
} from "@/lib/observability-types";

export const ENTRY_SELECT = `
SELECT
  e.entry_id,
  e.operation_id,
  e.subject_id,
  e.stage_id,
  e.entry_kind,
  e.log_level,
  e.logger_name,
  e.title,
  e.message,
  e.payload_json,
  e.payload_text,
  e.payload_hash,
  e.payload_bytes,
  e.payload_truncated,
  e.sanitized,
  e.http_method,
  e.url,
  e.route,
  e.status_code,
  e.error_code,
  e.error_class,
  e.stacktrace,
  e.attrs,
  e.occurred_at,
  e.stage_key,
  e.stage_label,
  e.stage_status,
  e.subject_type,
  e.subject_key,
  e.subject_display_name,
  e.subject_status,
  e.operation_key,
  e.batch_id,
  e.dependency,
  e.context_result,
  e.attempt_count,
  e.retryable,
  e.repair_manifest,
  e.raw_payload_id,
  e.raw_payload_available,
  e.raw_payload_truncated
FROM observability.v_stage_entry_enriched e
`;

export const OPERATION_SUMMARY_SELECT = `
SELECT
  op.operation_id,
  op.operation_key,
  op.route,
  op.method,
  op.client_ip,
  op.id_user,
  op.batch_size,
  op.http_status_code,
  op.operation_status,
  op.request_content_type,
  op.request_size_bytes,
  op.response_content_type,
  op.response_size_bytes,
  op.started_at,
  op.finished_at,
  op.duration_ms,
  op.error_message,
  op.attrs,
  op.batch_id,
  op.error_count,
  op.subject_count,
  op.stage_count,
  op.context_busy_count,
  op.context_conflict_count,
  op.context_release_count,
  op.context_finalize_count,
  op.repair_error_count,
  op.repair_count,
  op.pending_repair_count,
  op.related_operation_count
FROM observability.v_operation_enriched op
`;

export function paginate(page?: number, pageSize?: number) {
  const safePage = Math.max(1, page ?? 1);
  const safePageSize = Math.min(100, Math.max(1, pageSize ?? 25));
  const offset = (safePage - 1) * safePageSize;
  return { page: safePage, pageSize: safePageSize, offset };
}

export function buildPaginatedResult<T>(rows: T[], total: number, page: number, pageSize: number): PaginatedResult<T> {
  return {
    rows,
    total,
    page,
    pageSize,
    totalPages: Math.max(1, Math.ceil(total / pageSize)),
  };
}

export function normalizeSortDirection(value?: string): "asc" | "desc" {
  return value === "asc" ? "asc" : "desc";
}

export async function getDistinctOperationKeys(): Promise<string[]> {
  const res = await query<{ operation_key: string }>("SELECT DISTINCT operation_key FROM observability.operation_run ORDER BY operation_key");
  return res.rows.map((row) => row.operation_key);
}

export async function getDistinctStageKeys(): Promise<string[]> {
  const res = await query<{ stage_key: string }>("SELECT DISTINCT stage_key FROM observability.stage_run ORDER BY stage_key");
  return res.rows.map((row) => row.stage_key);
}

export async function getDistinctLoggerNames(): Promise<string[]> {
  const res = await query<{ logger_name: string }>("SELECT DISTINCT logger_name FROM observability.stage_entry WHERE logger_name IS NOT NULL ORDER BY logger_name");
  return res.rows.map((row) => row.logger_name);
}

export async function getDistinctErrorCodes(): Promise<string[]> {
  const res = await query<{ error_code: string }>("SELECT DISTINCT error_code FROM observability.stage_entry WHERE error_code IS NOT NULL ORDER BY error_code");
  return res.rows.map((row) => row.error_code);
}

export async function getDistinctDependencies(): Promise<string[]> {
  const res = await query<{ dependency: string }>(
    "SELECT DISTINCT dependency FROM observability.v_stage_entry_enriched WHERE dependency IS NOT NULL ORDER BY dependency",
  );
  return res.rows.map((row) => row.dependency);
}

export async function getDistinctContextResults(): Promise<string[]> {
  const res = await query<{ context_result: string }>(
    "SELECT DISTINCT context_result FROM observability.v_stage_entry_enriched WHERE context_result IS NOT NULL ORDER BY context_result",
  );
  return res.rows.map((row) => row.context_result);
}

export async function getEntries(filters: EntryFilters): Promise<PaginatedResult<EntryRow>> {
  const conditions: string[] = [];
  const params: unknown[] = [];
  let idx = 1;

  if (filters.operation_id) {
    conditions.push(`e.operation_id = $${idx++}`);
    params.push(filters.operation_id);
  }
  if (filters.subject_type) {
    conditions.push(`e.subject_type = $${idx++}`);
    params.push(filters.subject_type);
  }
  if (filters.subject_key) {
    conditions.push(`e.subject_key = $${idx++}`);
    params.push(filters.subject_key);
  }
  if (filters.document_id) {
    conditions.push(`e.subject_type = 'document' AND e.subject_key = $${idx++}`);
    params.push(filters.document_id);
  }
  if (filters.expediente_key) {
    conditions.push(`e.subject_type = 'expediente' AND e.subject_key = $${idx++}`);
    params.push(filters.expediente_key);
  }
  if (filters.batch_id) {
    conditions.push(`e.batch_id = $${idx++}`);
    params.push(filters.batch_id);
  }
  if (filters.stage_key) {
    conditions.push(`e.stage_key = $${idx++}`);
    params.push(filters.stage_key);
  }
  if (filters.operation_key) {
    conditions.push(`e.operation_key = $${idx++}`);
    params.push(filters.operation_key);
  }
  if (filters.entry_kinds && filters.entry_kinds.length > 0) {
    conditions.push(`e.entry_kind = ANY($${idx++})`);
    params.push(filters.entry_kinds);
  }
  if (filters.entry_kind) {
    conditions.push(`e.entry_kind = $${idx++}`);
    params.push(filters.entry_kind);
  }
  if (filters.log_level) {
    conditions.push(`e.log_level = $${idx++}`);
    params.push(filters.log_level);
  }
  if (filters.logger_name) {
    conditions.push(`e.logger_name = $${idx++}`);
    params.push(filters.logger_name);
  }
  if (filters.error_code) {
    conditions.push(`e.error_code = $${idx++}`);
    params.push(filters.error_code);
  }
  if (filters.dependency) {
    conditions.push(`e.dependency = $${idx++}`);
    params.push(filters.dependency);
  }
  if (filters.payload_hash) {
    conditions.push(`e.payload_hash = $${idx++}`);
    params.push(filters.payload_hash);
  }
  if (typeof filters.retryable === "boolean") {
    conditions.push(`COALESCE(e.retryable, false) = $${idx++}`);
    params.push(filters.retryable);
  }
  if (filters.context_result) {
    conditions.push(`e.context_result = $${idx++}`);
    params.push(filters.context_result);
  }
  if (typeof filters.attempt_count === "number") {
    conditions.push(`COALESCE(e.attempt_count, -1) = $${idx++}`);
    params.push(filters.attempt_count);
  }
  if (filters.status) {
    conditions.push(`COALESCE(e.stage_status, e.subject_status) = $${idx++}`);
    params.push(filters.status);
  }
  if (filters.from) {
    conditions.push(`e.occurred_at >= $${idx++}`);
    params.push(filters.from);
  }
  if (filters.to) {
    conditions.push(`e.occurred_at <= $${idx++}`);
    params.push(filters.to);
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
  const { page, pageSize, offset } = paginate(filters.page, filters.pageSize);
  const direction = normalizeSortDirection(filters.sortDirection);

  const [countRes, rowsRes] = await Promise.all([
    query(`SELECT COUNT(*)::int AS cnt FROM observability.v_stage_entry_enriched e ${where}`, params),
    query<EntryRow>(
      `${ENTRY_SELECT}
       ${where}
       ORDER BY e.occurred_at ${direction}, e.entry_id::bigint ${direction}
       LIMIT $${idx++} OFFSET $${idx++}`,
      [...params, pageSize, offset],
    ),
  ]);

  return buildPaginatedResult(rowsRes.rows, countRes.rows[0].cnt, page, pageSize);
}

export async function getOperationsV2(filters: {
  status?: string;
  operation_key?: string;
  batch_id?: string;
  from?: string;
  to?: string;
  page?: number;
  pageSize?: number;
}): Promise<PaginatedResult<OperationTraceSummary>> {
  const conditions: string[] = [];
  const params: unknown[] = [];
  let idx = 1;

  if (filters.status) {
    conditions.push(`op.operation_status = $${idx++}`);
    params.push(filters.status);
  }
  if (filters.operation_key) {
    conditions.push(`op.operation_key = $${idx++}`);
    params.push(filters.operation_key);
  }
  if (filters.batch_id) {
    conditions.push(`op.batch_id = $${idx++}`);
    params.push(filters.batch_id);
  }
  if (filters.from) {
    conditions.push(`op.started_at >= $${idx++}`);
    params.push(filters.from);
  }
  if (filters.to) {
    conditions.push(`op.started_at <= $${idx++}`);
    params.push(filters.to);
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
  const { page, pageSize, offset } = paginate(filters.page, filters.pageSize);

  const [countRes, rowsRes] = await Promise.all([
    query(`SELECT COUNT(*)::int AS cnt FROM observability.v_operation_enriched op ${where}`, params),
    query<OperationTraceSummary>(
      `${OPERATION_SUMMARY_SELECT}
       ${where}
       ORDER BY op.started_at DESC
       LIMIT $${idx++} OFFSET $${idx++}`,
      [...params, pageSize, offset],
    ),
  ]);

  return buildPaginatedResult(rowsRes.rows, countRes.rows[0].cnt, page, pageSize);
}

export async function getSubjects(filters: {
  subjectType?: string;
  subject_key?: string;
  batch_id?: string;
  status?: string;
  operation_key?: string;
  from?: string;
  to?: string;
  page?: number;
  pageSize?: number;
}): Promise<PaginatedResult<SubjectSummary>> {
  const conditions: string[] = [];
  const params: unknown[] = [];
  let idx = 1;

  if (filters.subjectType) {
    conditions.push(`subj.subject_type = $${idx++}`);
    params.push(filters.subjectType);
  }
  if (filters.subject_key) {
    conditions.push(`subj.subject_key = $${idx++}`);
    params.push(filters.subject_key);
  }
  if (filters.batch_id) {
    conditions.push(`COALESCE(subj.attrs ->> 'batch_id', op.batch_id) = $${idx++}`);
    params.push(filters.batch_id);
  }
  if (filters.status) {
    conditions.push(`subj.subject_status = $${idx++}`);
    params.push(filters.status);
  }
  if (filters.operation_key) {
    conditions.push(`op.operation_key = $${idx++}`);
    params.push(filters.operation_key);
  }
  if (filters.from) {
    conditions.push(`subj.started_at >= $${idx++}`);
    params.push(filters.from);
  }
  if (filters.to) {
    conditions.push(`subj.started_at <= $${idx++}`);
    params.push(filters.to);
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
  const { page, pageSize, offset } = paginate(filters.page, filters.pageSize);

  const subjectSelect = `
    SELECT
      subj.subject_id::text,
      subj.operation_id::text,
      subj.parent_subject_id::text,
      subj.subject_type,
      subj.subject_key,
      subj.display_name,
      subj.id_user,
      subj.subject_status,
      subj.started_at,
      subj.finished_at,
      subj.duration_ms,
      subj.error_message,
      subj.attrs,
      op.operation_key,
      op.route,
      op.method,
      op.http_status_code,
      op.operation_status,
      op.batch_id
    FROM observability.operation_subject subj
    JOIN observability.v_operation_enriched op ON op.operation_id::uuid = subj.operation_id
  `;

  const [countRes, rowsRes] = await Promise.all([
    query(`SELECT COUNT(*)::int AS cnt FROM observability.operation_subject subj JOIN observability.v_operation_enriched op ON op.operation_id::uuid = subj.operation_id ${where}`, params),
    query<SubjectSummary>(
      `${subjectSelect}
       ${where}
       ORDER BY subj.started_at DESC
       LIMIT $${idx++} OFFSET $${idx++}`,
      [...params, pageSize, offset],
    ),
  ]);

  return buildPaginatedResult(rowsRes.rows, countRes.rows[0].cnt, page, pageSize);
}

export async function getStageRowsByOperation(operationId: string): Promise<StageRunRow[]> {
  return (
    await query<StageRunRow>(
      `
      SELECT
        st.stage_id::text,
        st.operation_id::text,
        st.subject_id::text,
        st.parent_stage_id::text,
        st.stage_key,
        st.stage_label,
        st.stage_status,
        st.started_at,
        st.finished_at,
        st.duration_ms,
        st.error_message,
        st.error_class,
        st.attrs,
        subj.subject_key,
        subj.subject_type,
        subj.display_name,
        COALESCE(st.attrs ->> 'batch_id', subj.attrs ->> 'batch_id', op.batch_id) AS batch_id,
        st.attrs ->> 'dependency' AS dependency,
        st.attrs ->> 'context_result' AS context_result,
        CASE
          WHEN st.attrs ? 'attempt_count' AND (st.attrs ->> 'attempt_count') ~ '^-?[0-9]+$'
          THEN (st.attrs ->> 'attempt_count')::int
          ELSE NULL
        END AS attempt_count
      FROM observability.stage_run st
      LEFT JOIN observability.operation_subject subj ON subj.subject_id = st.subject_id
      JOIN observability.v_operation_enriched op ON op.operation_id::uuid = st.operation_id
      WHERE st.operation_id = $1
      ORDER BY st.started_at ASC, st.stage_id ASC
      `,
      [operationId],
    )
  ).rows;
}
