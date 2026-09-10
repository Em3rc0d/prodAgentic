import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const API = (
  process.env.PRODAGENTIC_INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"
).replace(/\/$/, "");

export async function GET() {
  try {
    const response = await fetch(`${API}/health/ready`, { cache: "no-store" });
    const payload = await response.json().catch(() => null);
    return NextResponse.json({
      reachable: true,
      ready: response.ok,
      upstream_status: response.status,
      status: payload?.status ?? null,
      detail: payload?.message ?? payload?.detail ?? null,
    }, { status: 200, headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return NextResponse.json({
      reachable: false,
      ready: false,
      upstream_status: null,
      status: null,
      detail: error instanceof Error ? error.message : "Backend readiness endpoint is unreachable.",
    }, { status: 200, headers: { "Cache-Control": "no-store" } });
  }
}
