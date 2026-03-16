import { NextResponse } from "next/server";
import { requireAdminSession } from "@/lib/auth";
import { query } from "@/lib/db";
import { revealPayloadVaultEntry } from "@/lib/payload-vault";

export async function POST(
  request: Request,
  context: { params: Promise<{ vaultId: string }> },
) {
  try {
    const user = await requireAdminSession();
    const { vaultId } = await context.params;
    const numericVaultId = Number(vaultId);
    if (!Number.isFinite(numericVaultId)) {
      return NextResponse.json({ error: "Vault inválido" }, { status: 400 });
    }

    const body = await request.json().catch(() => ({}));
    const reason = typeof body.reason === "string" ? body.reason.slice(0, 200) : "dashboard-reveal";
    const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? null;
    const payload = await revealPayloadVaultEntry(numericVaultId);

    await query(
      `
      INSERT INTO observability.payload_reveal_audit (vault_id, username, action, reason, client_ip, attrs)
      VALUES ($1, $2, 'reveal', $3, $4, $5::jsonb)
      `,
      [numericVaultId, user.username, reason, ip, JSON.stringify({ route: "api/payload-vault/reveal" })],
    );

    return NextResponse.json(payload);
  } catch (error) {
    if (error instanceof Error && error.message === "forbidden") {
      return NextResponse.json({ error: "No autorizado" }, { status: 403 });
    }
    if (error instanceof Error && error.message === "not_found") {
      return NextResponse.json({ error: "Payload no encontrado" }, { status: 404 });
    }
    console.error("Payload reveal failed", error);
    return NextResponse.json({ error: "Error interno" }, { status: 500 });
  }
}
