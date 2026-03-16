import { query } from "@/lib/db";
import type {
  BatchSummary,
  BatchTrace,
  DependencySummary,
  EntryRow,
  OperationTimelineItem,
  OperationTraceSummary,
  OperationTraceDetail,
  OverviewStatsV2,
  PaginatedResult,
  PayloadCompareResult,
  PayloadVaultMetadata,
  RepairSummary,
  RuntimeStatusRow,
  StageRunRow,
  SubjectSummary,
  SubjectHistory,
} from "@/lib/observability-types";
import {
  buildPaginatedResult,
  ENTRY_SELECT,
  getEntries,
  getOperationsV2,
  getStageRowsByOperation,
  getSubjects,
  normalizeSortDirection,
  OPERATION_SUMMARY_SELECT,
  paginate,
} from "@/lib/observability-query-utils";

function buildTimeline(rows: EntryRow[], stages: OperationTraceDetail["stages"]): OperationTimelineItem[] {
  const items: OperationTimelineItem[] = [];
  for (const stage of stages) {
    items.push({
      timeline_id: `stage-start-${stage.stage_id}`,
      timeline_kind: "stage_start",
      occurred_at: stage.started_at,
      sort_key: `${stage.started_at}-0-${stage.stage_id}`,
      stage_id: stage.stage_id,
      stage_key: stage.stage_key,
      stage_label: stage.stage_label,
      stage_status: stage.stage_status,
      title: `Inicio ${stage.stage_label}`,
      message: stage.error_message,
      entry: null,
      stage,
    });
    if (stage.finished_at) {
      items.push({
        timeline_id: `stage-finish-${stage.stage_id}`,
        timeline_kind: "stage_finish",
        occurred_at: stage.finished_at,
        sort_key: `${stage.finished_at}-2-${stage.stage_id}`,
        stage_id: stage.stage_id,
        stage_key: stage.stage_key,
        stage_label: stage.stage_label,
        stage_status: stage.stage_status,
        title: `Fin ${stage.stage_label}`,
        message: stage.error_message,
        entry: null,
        stage,
      });
    }
  }
  for (const entry of rows) {
    items.push({
      timeline_id: `entry-${entry.entry_id}`,
      timeline_kind: "entry",
      occurred_at: entry.occurred_at,
      sort_key: `${entry.occurred_at}-1-${entry.entry_id}`,
      stage_id: entry.stage_id,
      stage_key: entry.stage_key,
      stage_label: entry.stage_label,
      stage_status: entry.stage_status,
      title: entry.title ?? entry.entry_kind,
      message: entry.message,
      entry,
      stage: null,
    });
  }
  return items.sort((left, right) => left.sort_key.localeCompare(right.sort_key));
}

export async function getOverviewStatsV2(): Promise<OverviewStatsV2> {
  const [opsRes, subjectsRes, entriesRes, errRes, retryRes, repairRes, conflictRes, busyRes, topRes, slowRes, recentRes, repairsRes, runtimeRes, depRes, batchRes] = await Promise.all([
    query("SELECT COUNT(*)::int AS cnt FROM observability.operation_run WHERE started_at > NOW() - INTERVAL '24 hours'"),
    query("SELECT COUNT(*)::int AS cnt FROM observability.operation_subject WHERE started_at > NOW() - INTERVAL '24 hours'"),
    query("SELECT COUNT(*)::int AS cnt FROM observability.stage_entry WHERE occurred_at > NOW() - INTERVAL '24 hours'"),
    query("SELECT COUNT(*)::int AS cnt FROM observability.stage_entry WHERE entry_kind = 'error' AND occurred_at > NOW() - INTERVAL '24 hours'"),
    query("SELECT COUNT(*)::int AS cnt FROM observability.v_stage_entry_enriched WHERE attempt_count IS NOT NULL AND attempt_count > 0 AND occurred_at > NOW() - INTERVAL '24 hours'"),
    query("SELECT COUNT(*)::int AS cnt FROM observability.v_repair_backlog WHERE status = 'pending'"),
    query("SELECT COUNT(*)::int AS cnt FROM observability.v_stage_entry_enriched WHERE context_result = 'conflict' AND occurred_at > NOW() - INTERVAL '24 hours'"),
    query("SELECT COUNT(*)::int AS cnt FROM observability.v_stage_entry_enriched WHERE context_result = 'busy' AND occurred_at > NOW() - INTERVAL '24 hours'"),
    query<{ stage_key: string; cnt: number }>(
      `
      SELECT COALESCE(stage_key, 'sin_etapa') AS stage_key, COUNT(*)::int AS cnt
      FROM observability.v_stage_entry_enriched
      WHERE entry_kind = 'error' AND occurred_at > NOW() - INTERVAL '24 hours'
      GROUP BY COALESCE(stage_key, 'sin_etapa')
      ORDER BY cnt DESC
      LIMIT 6
      `,
    ),
    query<{ stage_key: string; avg_ms: number; p95_ms: number; max_ms: number }>(
      `
      SELECT
        stage_key,
        ROUND(AVG(duration_ms)::numeric, 2)::float8 AS avg_ms,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 2)::float8 AS p95_ms,
        MAX(duration_ms)::int AS max_ms
      FROM observability.stage_run
      WHERE duration_ms IS NOT NULL AND started_at > NOW() - INTERVAL '24 hours'
      GROUP BY stage_key
      ORDER BY p95_ms DESC NULLS LAST
      LIMIT 8
      `,
    ),
    query<EntryRow>(
      `${ENTRY_SELECT}
       WHERE e.entry_kind = 'error' AND e.occurred_at > NOW() - INTERVAL '24 hours'
       ORDER BY e.occurred_at DESC, e.entry_id DESC
       LIMIT 12`,
    ),
    query<RepairSummary>(
      `
      SELECT *
      FROM observability.v_repair_backlog
      ORDER BY CASE WHEN status = 'pending' THEN 0 ELSE 1 END, created_at DESC
      LIMIT 8
      `,
    ),
    query<RuntimeStatusRow>("SELECT * FROM observability.runtime_status ORDER BY updated_at DESC"),
    query<DependencySummary>(
      `
      WITH base AS (
        SELECT
          COALESCE(dependency, 'internal') AS dependency,
          COUNT(*)::int AS entry_count,
          COUNT(*) FILTER (WHERE entry_kind = 'error' OR log_level = 'error')::int AS error_count,
          ROUND(AVG(COALESCE((attrs ->> 'duration_ms')::numeric, 0))::numeric, 2)::float8 AS avg_duration_ms,
          ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY COALESCE((attrs ->> 'duration_ms')::numeric, 0))::numeric, 2)::float8 AS p95_duration_ms,
          MAX(occurred_at) AS last_seen_at
        FROM observability.v_stage_entry_enriched
        WHERE dependency IS NOT NULL
        GROUP BY COALESCE(dependency, 'internal')
      ),
      status_codes AS (
        SELECT dependency, jsonb_object_agg(status_code::text, cnt) AS status_codes
        FROM (
          SELECT COALESCE(dependency, 'internal') AS dependency, status_code, COUNT(*)::int AS cnt
          FROM observability.v_stage_entry_enriched
          WHERE dependency IS NOT NULL AND status_code IS NOT NULL
          GROUP BY COALESCE(dependency, 'internal'), status_code
        ) grouped
        GROUP BY dependency
      )
      SELECT
        base.dependency,
        base.entry_count,
        base.error_count,
        base.avg_duration_ms,
        base.p95_duration_ms,
        base.last_seen_at,
        COALESCE(status_codes.status_codes, '{}'::jsonb) AS status_codes
      FROM base
      LEFT JOIN status_codes ON status_codes.dependency = base.dependency
      ORDER BY base.error_count DESC, base.entry_count DESC
      `,
    ),
    query<BatchSummary>(
      `
      SELECT *
      FROM observability.v_batch_summary
      ORDER BY pending_repair_count DESC, error_count DESC, last_seen_at DESC
      LIMIT 8
      `,
    ),
  ]);

  return {
    total_operations_24h: opsRes.rows[0].cnt,
    total_subjects_24h: subjectsRes.rows[0].cnt,
    total_entries_24h: entriesRes.rows[0].cnt,
    error_count_24h: errRes.rows[0].cnt,
    retry_count_24h: retryRes.rows[0].cnt,
    pending_repair_count: repairRes.rows[0].cnt,
    context_conflict_count: conflictRes.rows[0].cnt,
    context_busy_count: busyRes.rows[0].cnt,
    top_error_stages: topRes.rows,
    slow_stages: slowRes.rows,
    recent_errors: recentRes.rows,
    critical_repairs: repairsRes.rows,
    batch_watchlist: batchRes.rows,
    runtime_status: runtimeRes.rows,
    dependency_summary: depRes.rows.map((row) => ({ ...row, status_codes: row.status_codes ?? {} })),
  };
}

export async function getOperationTrace(
  operationId: string,
  options?: {
    page?: number;
    pageSize?: number;
    timelinePage?: number;
    timelinePageSize?: number;
    entryKinds?: string[];
    sortDirection?: "asc" | "desc";
  },
): Promise<OperationTraceDetail> {
  const direction = normalizeSortDirection(options?.sortDirection ?? "asc");
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
    WHERE subj.operation_id = $1
    ORDER BY subj.started_at ASC, subj.subject_id ASC
  `;
  const countsSelect = `
    SELECT
      COUNT(*)::int AS total,
      COUNT(*) FILTER (WHERE entry_kind = 'http_request' OR entry_kind = 'external_request')::int AS requests,
      COUNT(*) FILTER (WHERE entry_kind = 'http_response' OR entry_kind = 'external_response')::int AS responses,
      COUNT(*) FILTER (WHERE entry_kind = 'app_log')::int AS logs,
      COUNT(*) FILTER (WHERE entry_kind = 'error')::int AS errors
    FROM observability.v_stage_entry_enriched
    WHERE operation_id = $1
  `;

  const [operationRes, subjectsRes, stages, entriesRes, countsRes, timelineEntries] = await Promise.all([
    query<OperationTraceSummary>(`${OPERATION_SUMMARY_SELECT} WHERE op.operation_id = $1`, [operationId]),
    query<SubjectSummary>(subjectSelect, [operationId]),
    getStageRowsByOperation(operationId),
    getEntries({
      operation_id: operationId,
      entry_kinds: options?.entryKinds,
      page: options?.page ?? 1,
      pageSize: options?.pageSize ?? 25,
      sortDirection: direction,
    }),
    query<{ total: number; requests: number; responses: number; logs: number; errors: number }>(countsSelect, [operationId]),
    getEntries({
      operation_id: operationId,
      page: options?.timelinePage ?? 1,
      pageSize: options?.timelinePageSize ?? 250,
      sortDirection: "asc",
    }),
  ]);

  const fullTimelineBase = buildTimeline(timelineEntries.rows, stages);
  const fullTimeline = direction === "desc" ? [...fullTimelineBase].reverse() : fullTimelineBase;
  const timelinePage = paginate(options?.timelinePage ?? 1, options?.timelinePageSize ?? 250);
  const timelineRows = fullTimeline.slice(timelinePage.offset, timelinePage.offset + timelinePage.pageSize);

  return {
    operation: operationRes.rows[0] ?? null,
    subjects: subjectsRes.rows,
    stages,
    entries: entriesRes,
    timeline: buildPaginatedResult(timelineRows, fullTimeline.length, timelinePage.page, timelinePage.pageSize),
    counts: countsRes.rows[0] ?? { total: 0, requests: 0, responses: 0, logs: 0, errors: 0 },
  };
}

export async function getSubjectHistory(
  subjectType: string,
  subjectKey: string,
  options?: {
    page?: number;
    pageSize?: number;
    sortDirection?: "asc" | "desc";
  },
): Promise<SubjectHistory> {
  const subjectWhere = `WHERE subj.subject_type = $1 AND subj.subject_key = $2`;
  const direction = normalizeSortDirection(options?.sortDirection ?? "asc");

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

  const [subjectsRes, stagesRes, entriesRes] = await Promise.all([
    query<SubjectSummary>(`${subjectSelect} ${subjectWhere} ORDER BY subj.started_at ASC`, [subjectType, subjectKey]),
    query<StageRunRow>(
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
      JOIN observability.operation_subject subj ON subj.subject_id = st.subject_id
      JOIN observability.v_operation_enriched op ON op.operation_id::uuid = st.operation_id
      ${subjectWhere}
      ORDER BY st.started_at ASC, st.stage_id ASC
      `,
      [subjectType, subjectKey],
    ),
    getEntries({
      subject_type: subjectType,
      subject_key: subjectKey,
      page: options?.page ?? 1,
      pageSize: options?.pageSize ?? 25,
      sortDirection: direction,
    }),
  ]);

  return {
    subjects: subjectsRes.rows,
    stages: stagesRes.rows,
    entries: entriesRes,
  };
}

export async function getBatchSummaries(filters?: {
  page?: number;
  pageSize?: number;
  batch_id?: string;
}): Promise<PaginatedResult<BatchSummary>> {
  const conditions: string[] = [];
  const params: unknown[] = [];
  let idx = 1;
  if (filters?.batch_id) {
    conditions.push(`batch_id = $${idx++}`);
    params.push(filters.batch_id);
  }
  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
  const { page, pageSize, offset } = paginate(filters?.page, filters?.pageSize);
  const [countRes, rowsRes] = await Promise.all([
    query(`SELECT COUNT(*)::int AS cnt FROM observability.v_batch_summary ${where}`, params),
    query<BatchSummary>(
      `SELECT * FROM observability.v_batch_summary ${where} ORDER BY pending_repair_count DESC, error_count DESC, last_seen_at DESC LIMIT $${idx++} OFFSET $${idx++}`,
      [...params, pageSize, offset],
    ),
  ]);
  return buildPaginatedResult(rowsRes.rows, countRes.rows[0].cnt, page, pageSize);
}

export async function getBatchTrace(
  batchId: string,
  options?: { page?: number; pageSize?: number; entryPage?: number; entryPageSize?: number },
): Promise<BatchTrace> {
  const [summaryRes, operations, subjects, entries] = await Promise.all([
    query<BatchSummary>("SELECT * FROM observability.v_batch_summary WHERE batch_id = $1", [batchId]),
    getOperationsV2({ batch_id: batchId, page: options?.page ?? 1, pageSize: options?.pageSize ?? 25 }),
    getSubjects({ batch_id: batchId, page: options?.page ?? 1, pageSize: options?.pageSize ?? 25 }),
    getEntries({ batch_id: batchId, page: options?.entryPage ?? 1, pageSize: options?.entryPageSize ?? 50, sortDirection: "desc" }),
  ]);
  return {
    summary: summaryRes.rows[0] ?? null,
    operations,
    subjects,
    entries,
  };
}

export async function getRepairBacklog(filters?: {
  page?: number;
  pageSize?: number;
  status?: string;
  batch_id?: string;
}): Promise<PaginatedResult<RepairSummary>> {
  const conditions: string[] = [];
  const params: unknown[] = [];
  let idx = 1;
  if (filters?.status) {
    conditions.push(`status = $${idx++}`);
    params.push(filters.status);
  }
  if (filters?.batch_id) {
    conditions.push(`batch_id = $${idx++}`);
    params.push(filters.batch_id);
  }
  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
  const { page, pageSize, offset } = paginate(filters?.page, filters?.pageSize);
  const [countRes, rowsRes] = await Promise.all([
    query(`SELECT COUNT(*)::int AS cnt FROM observability.v_repair_backlog ${where}`, params),
    query<RepairSummary>(
      `SELECT * FROM observability.v_repair_backlog ${where} ORDER BY CASE WHEN status = 'pending' THEN 0 ELSE 1 END, created_at DESC LIMIT $${idx++} OFFSET $${idx++}`,
      [...params, pageSize, offset],
    ),
  ]);
  return buildPaginatedResult(rowsRes.rows, countRes.rows[0].cnt, page, pageSize);
}

export async function getDependencySummary(): Promise<DependencySummary[]> {
  return (await getOverviewStatsV2()).dependency_summary;
}

export async function getRuntimeStatus(): Promise<RuntimeStatusRow[]> {
  return (await query<RuntimeStatusRow>("SELECT * FROM observability.runtime_status ORDER BY updated_at DESC")).rows;
}

export async function getPayloadVaultMetadata(vaultId: number): Promise<PayloadVaultMetadata | null> {
  const res = await query<PayloadVaultMetadata>(
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
  return res.rows[0] ?? null;
}

export async function comparePayloadVaultEntries(leftVaultId: number, rightVaultId: number): Promise<PayloadCompareResult | null> {
  const [left, right] = await Promise.all([getPayloadVaultMetadata(leftVaultId), getPayloadVaultMetadata(rightVaultId)]);
  if (!left || !right) {
    return null;
  }

  return {
    left,
    right,
    same_hash: left.payload_hash === right.payload_hash,
    same_size: left.raw_bytes === right.raw_bytes,
    same_content_kind: left.content_kind === right.content_kind,
    text_diff: null,
  };
}
