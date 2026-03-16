import { NextResponse } from "next/server";
import { requireAdminSession } from "@/lib/auth";
import { query } from "@/lib/db";
import { buildPayloadCompare, revealPayloadVaultEntry } from "@/lib/payload-vault";

export async function POST(request: Request) {
  try {
    const user = await requireAdminSession();
    const body = await request.json();
    const leftVaultId = Number(body?.leftVaultId);
    const rightVaultId = Number(body?.rightVaultId);
    const reason = typeof body?.reason === "string" ? body.reason.slice(0, 200) : "dashboard-compare";
    if (!Number.isFinite(leftVaultId) || !Number.isFinite(rightVaultId)) {
      return NextResponse.json({ error: "Vault inválido" }, { status: 400 });
    }

    const [left, right] = await Promise.all([
      revealPayloadVaultEntry(leftVaultId),
      revealPayloadVaultEntry(rightVaultId),
    ]);
    const compare = buildPayloadCompare(left, right);
    const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? null;

    await query(
      `
      INSERT INTO observability.payload_reveal_audit (vault_id, username, action, reason, client_ip, attrs)
      VALUES
        ($1, $2, 'compare', $3, $4, $5::jsonb),
        ($6, $2, 'compare', $3, $4, $7::jsonb)
      `,
      [
        leftVaultId,
        user.username,
        reason,
        ip,
        JSON.stringify({ peer_vault_id: rightVaultId }),
        rightVaultId,
        JSON.stringify({ peer_vault_id: leftVaultId }),
      ],
    );

    return NextResponse.json(compare);
  } catch (error) {
    if (error instanceof Error && error.message === "forbidden") {
      return NextResponse.json({ error: "No autorizado" }, { status: 403 });
    }
    console.error("Payload compare failed", error);
    return NextResponse.json({ error: "Error interno" }, { status: 500 });
  }
}
