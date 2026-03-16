import { NextResponse } from "next/server";
import { query } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const res = await query("SELECT 1 AS ok");
    if (res.rows[0]?.ok === 1) {
      return NextResponse.json({ status: "healthy", db: "connected" });
    }
    return NextResponse.json({ status: "unhealthy", db: "unexpected" }, { status: 503 });
  } catch (err) {
    console.error("Health check failed:", err);
    return NextResponse.json(
      { status: "unhealthy", db: "disconnected" },
      { status: 503 },
    );
  }
}
