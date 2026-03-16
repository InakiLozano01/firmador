import { NextResponse } from "next/server";
import {
  ensureAdminExists,
  authenticate,
  createSession,
  auditLogin,
} from "@/lib/auth";

export async function POST(request: Request) {
  try {
    await ensureAdminExists();
  } catch (bootstrapErr) {
    console.error("Admin bootstrap failed:", bootstrapErr);
    return NextResponse.json(
      { error: "Error interno" },
      { status: 500 },
    );
  }

  try {
    const { username, password } = await request.json();
    if (!username || !password) {
      return NextResponse.json(
        { error: "Usuario y contraseña requeridos" },
        { status: 400 },
      );
    }

    const ip =
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? null;
    const ua = request.headers.get("user-agent");

    const user = await authenticate(username, password);

    if (!user) {
      await auditLogin(username, false, ip, ua);
      return NextResponse.json(
        { error: "Credenciales inválidas" },
        { status: 401 },
      );
    }

    const sessionId = await createSession(user.id);
    await auditLogin(username, true, ip, ua);

    const forwardedProto = request.headers
      .get("x-forwarded-proto")
      ?.split(",")[0]
      ?.trim()
      ?.toLowerCase();
    const requestProto = new URL(request.url).protocol.replace(":", "");
    const useSecureCookie = forwardedProto === "https" || requestProto === "https";
    const res = NextResponse.json({ ok: true, user: { username: user.username, role: user.role } });
    res.cookies.set("session_id", sessionId, {
      httpOnly: true,
      secure: useSecureCookie,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24,
    });

    return res;
  } catch (err) {
    console.error("Login error:", err);
    return NextResponse.json(
      { error: "Error interno" },
      { status: 500 },
    );
  }
}
