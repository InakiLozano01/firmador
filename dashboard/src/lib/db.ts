import { Pool, type QueryResultRow } from "pg";

const pool = new Pool({
  host: process.env.OBS_DB_HOST ?? "obs-postgres",
  port: Number(process.env.OBS_DB_PORT ?? 5432),
  database: process.env.OBS_DB_NAME ?? "obs_dashboard",
  user: process.env.OBS_DB_USER ?? "obs_user",
  password: process.env.OBS_DB_PASSWORD ?? "obs_password",
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
});

export async function query<T extends QueryResultRow = QueryResultRow>(
  text: string,
  params?: unknown[],
) {
  return pool.query<T>(text, params);
}

export { pool };
