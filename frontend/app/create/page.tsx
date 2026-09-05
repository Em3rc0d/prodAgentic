import Link from "next/link";

import { Mk1BatchCreate } from "@/components/mk1/Mk1BatchCreate";
import { mk1BatchPlanningEnabled } from "@/lib/mk1-feature-flags";

export default function CreatePage() {
  if (mk1BatchPlanningEnabled) return <Mk1BatchCreate />;

  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: "64px 24px", color: "var(--mk1-text, #f4f7fa)" }}>
      <p style={{ color: "var(--mk1-signal, #d8ff45)", textTransform: "uppercase", letterSpacing: ".12em", fontSize: 12 }}>Create</p>
      <h1 style={{ fontSize: 42, letterSpacing: "-.04em", marginBottom: 12 }}>Batch planning is not enabled.</h1>
      <p style={{ color: "var(--mk1-text-muted, #a5afbc)", lineHeight: 1.6 }}>Profile V2 can remain active independently. Enable the S2 planning gate only after its certification is accepted.</p>
      <Link href="/profiles" prefetch={false} style={{ display: "inline-block", marginTop: 20, color: "var(--mk1-signal, #d8ff45)" }}>Go to Profiles</Link>
    </main>
  );
}
