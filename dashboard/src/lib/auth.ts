import { cookies } from "next/headers";
import { query } from "./db";
import bcrypt from "bcryptjs";
import crypto from "crypto";

const SESSION_DURATION_MS = 24 * 60 * 60 * 1000; // 24 hours

export interface SessionUser {
  id: number;
  username: string;
  role: string;
}

export async function ensureAdminExists() {
  const username = process.env.ADMIN_USERNAME;
  const password = process.env.ADMIN_PASSWORD;
  if (!username || !password) {
    console.warn("Dashboard admin bootstrap skipped: ADMIN_USERNAME/ADMIN_PASSWORD not configured");
    return;
  }

  const hash = await bcrypt.hash(password, 12);
  await query(
    `
    INSERT INTO dashboard_auth.users (username, password_hash, role)
    VALUES ($1, $2, 'admin')
    ON CONFLICT (username) DO NOTHING
    `,
    [username, hash],
  );
}

export async function authenticate(
  username: string,
  password: string,
): Promise<SessionUser | null> {
  const res = await query(
    "SELECT id, username, password_hash, role FROM dashboard_auth.users WHERE username = $1",
    [username],
  );
  if (res.rows.length === 0) return null;

  const user = res.rows[0];
  const valid = await bcrypt.compare(password, user.password_hash);
  if (!valid) return null;

  return { id: user.id, username: user.username, role: user.role };
}

export async function createSession(userId: number): Promise<string> {
  const sessionId = crypto.randomUUID();
  const expiresAt = new Date(Date.now() + SESSION_DURATION_MS);
  await query(
    "INSERT INTO dashboard_auth.sessions (id, user_id, expires_at) VALUES ($1, $2, $3)",
    [sessionId, userId, expiresAt],
  );
  return sessionId;
}

export async function validateSession(): Promise<SessionUser | null> {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get("session_id")?.value;
  if (!sessionId) return null;

  const res = await query(
    `SELECT s.id, s.user_id, s.expires_at, u.username, u.role
     FROM dashboard_auth.sessions s
     JOIN dashboard_auth.users u ON u.id = s.user_id
     WHERE s.id = $1 AND s.expires_at > NOW()`,
    [sessionId],
  );

  if (res.rows.length === 0) return null;
  const row = res.rows[0];
  return { id: row.user_id, username: row.username, role: row.role };
}

export async function requireAdminSession(): Promise<SessionUser> {
  const user = await validateSession();
  if (!user || user.role !== "admin") {
    throw new Error("forbidden");
  }
  return user;
}

export async function destroySession(sessionId: string) {
  await query("DELETE FROM dashboard_auth.sessions WHERE id = $1", [sessionId]);
}

export async function auditLogin(
  username: string,
  success: boolean,
  ip: string | null,
  ua: string | null,
) {
  await query(
    "INSERT INTO dashboard_auth.audit_login (username, success, ip_address, user_agent) VALUES ($1, $2, $3, $4)",
    [username, success, ip, ua],
  );
}

export async function cleanExpiredSessions() {
  await query("DELETE FROM dashboard_auth.sessions WHERE expires_at < NOW()");
}
