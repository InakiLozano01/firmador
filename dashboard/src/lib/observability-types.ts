export interface PaginatedResult<T> {
  rows: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface OperationTraceSummary {
  operation_id: string;
  operation_key: string;
  route: string;
  method: string;
  client_ip: string | null;
  id_user: string | null;
  batch_size: number;
  http_status_code: number | null;
  operation_status: string;
  request_content_type: string | null;
  request_size_bytes: number | null;
  response_content_type: string | null;
  response_size_bytes: number | null;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  error_message: string | null;
  attrs: Record<string, unknown>;
  batch_id: string | null;
  error_count: number;
  subject_count: number;
  stage_count: number;
  context_busy_count: number;
  context_conflict_count: number;
  context_release_count: number;
  context_finalize_count: number;
  repair_error_count: number;
  repair_count: number;
  pending_repair_count: number;
  related_operation_count: number;
}

export interface SubjectSummary {
  subject_id: string;
  operation_id: string;
  parent_subject_id: string | null;
  subject_type: string;
  subject_key: string;
  display_name: string | null;
  id_user: string | null;
  subject_status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  error_message: string | null;
  attrs: Record<string, unknown>;
  operation_key: string;
  route: string;
  method: string;
  http_status_code: number | null;
  operation_status: string;
  batch_id: string | null;
}

export interface StageRunRow {
  stage_id: string;
  operation_id: string;
  subject_id: string | null;
  parent_stage_id: string | null;
  stage_key: string;
  stage_label: string;
  stage_status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  error_message: string | null;
  error_class: string | null;
  attrs: Record<string, unknown>;
  subject_key: string | null;
  subject_type: string | null;
  display_name: string | null;
  batch_id: string | null;
  dependency: string | null;
  context_result: string | null;
  attempt_count: number | null;
}

export interface EntryRow {
  entry_id: string;
  operation_id: string;
  subject_id: string | null;
  stage_id: string | null;
  entry_kind: string;
  log_level: string | null;
  logger_name: string | null;
  title: string | null;
  message: string | null;
  payload_json: Record<string, unknown> | unknown[] | null;
  payload_text: string | null;
  payload_hash: string | null;
  payload_bytes: number | null;
  payload_truncated: boolean;
  sanitized: boolean;
  http_method: string | null;
  url: string | null;
  route: string | null;
  status_code: number | null;
  error_code: string | null;
  error_class: string | null;
  stacktrace: string | null;
  attrs: Record<string, unknown>;
  occurred_at: string;
  stage_key: string | null;
  stage_label: string | null;
  stage_status: string | null;
  subject_type: string | null;
  subject_key: string | null;
  subject_display_name: string | null;
  subject_status: string | null;
  operation_key: string;
  batch_id: string | null;
  dependency: string | null;
  context_result: string | null;
  attempt_count: number | null;
  retryable: boolean | null;
  repair_manifest: string | null;
  raw_payload_id: number | null;
  raw_payload_available: boolean;
  raw_payload_truncated: boolean;
}

export interface OperationTimelineItem {
  timeline_id: string;
  timeline_kind: "entry" | "stage_start" | "stage_finish";
  occurred_at: string;
  sort_key: string;
  stage_id: string | null;
  stage_key: string | null;
  stage_label: string | null;
  stage_status: string | null;
  title: string;
  message: string | null;
  entry: EntryRow | null;
  stage: StageRunRow | null;
}

export interface OperationTraceDetail {
  operation: OperationTraceSummary | null;
  subjects: SubjectSummary[];
  stages: StageRunRow[];
  entries: PaginatedResult<EntryRow>;
  timeline: PaginatedResult<OperationTimelineItem>;
  counts: {
    total: number;
    requests: number;
    responses: number;
    logs: number;
    errors: number;
  };
}

export interface SubjectHistory {
  subjects: SubjectSummary[];
  stages: StageRunRow[];
  entries: PaginatedResult<EntryRow>;
}

export interface OverviewStatsV2 {
  total_operations_24h: number;
  total_subjects_24h: number;
  total_entries_24h: number;
  error_count_24h: number;
  retry_count_24h: number;
  pending_repair_count: number;
  context_conflict_count: number;
  context_busy_count: number;
  top_error_stages: { stage_key: string; cnt: number }[];
  slow_stages: { stage_key: string; avg_ms: number; p95_ms: number; max_ms: number }[];
  recent_errors: EntryRow[];
  critical_repairs: RepairSummary[];
  batch_watchlist: BatchSummary[];
  runtime_status: RuntimeStatusRow[];
  dependency_summary: DependencySummary[];
}

export interface BatchSummary {
  batch_id: string;
  first_seen_at: string;
  last_seen_at: string;
  operation_count: number;
  flagged_operation_count: number;
  document_count: number;
  expediente_count: number;
  error_count: number;
  repair_count: number;
  pending_repair_count: number;
  max_context_busy_count: number;
  max_context_conflict_count: number;
}

export interface BatchTrace {
  summary: BatchSummary | null;
  operations: PaginatedResult<OperationTraceSummary>;
  subjects: PaginatedResult<SubjectSummary>;
  entries: PaginatedResult<EntryRow>;
}

export interface RepairSummary {
  manifest_id: string;
  operation_id: string | null;
  id_doc: string | null;
  manifest_path: string;
  target_path: string;
  temp_path: string;
  hash_doc: string;
  payload_sha256: string;
  bytes_written: number | null;
  status: string;
  retryable: boolean;
  db_committed: boolean;
  created_at: string;
  recovered_at: string | null;
  last_error: string | null;
  attrs: Record<string, unknown>;
  operation_key: string | null;
  route: string | null;
  batch_id: string | null;
}

export interface DependencySummary {
  dependency: string;
  entry_count: number;
  error_count: number;
  avg_duration_ms: number | null;
  p95_duration_ms: number | null;
  last_seen_at: string | null;
  status_codes: Record<string, number>;
}

export interface RuntimeStatusRow {
  service_name: string;
  instance_id: string | null;
  queue_depth: number;
  dropped_events: number;
  last_flush_at: string | null;
  updated_at: string;
  attrs: Record<string, unknown>;
}

export interface PayloadVaultMetadata {
  vault_id: number;
  operation_id: string | null;
  subject_id: string | null;
  stage_id: string | null;
  entry_kind: string;
  route: string | null;
  stage_key: string | null;
  payload_hash: string;
  content_kind: string;
  algorithm: string;
  compression: string;
  raw_bytes: number;
  stored_bytes: number;
  truncated: boolean;
  created_at: string;
  expires_at: string;
  attrs: Record<string, unknown>;
}

export interface PayloadCompareResult {
  left: PayloadVaultMetadata;
  right: PayloadVaultMetadata;
  same_hash: boolean;
  same_size: boolean;
  same_content_kind: boolean;
  text_diff: string | null;
}

export interface EntryFilters {
  operation_id?: string;
  subject_type?: string;
  subject_key?: string;
  document_id?: string;
  expediente_key?: string;
  batch_id?: string;
  stage_key?: string;
  operation_key?: string;
  entry_kind?: string;
  entry_kinds?: string[];
  log_level?: string;
  logger_name?: string;
  error_code?: string;
  dependency?: string;
  payload_hash?: string;
  retryable?: boolean;
  context_result?: string;
  attempt_count?: number;
  status?: string;
  from?: string;
  to?: string;
  page?: number;
  pageSize?: number;
  sortDirection?: "asc" | "desc";
}
