"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchContentRun, resolveBackendAssetUrl, type ContentRun } from "@/lib/api";
import {
  extractClaims,
  matchAndEvaluateCurrentEvidence,
  reviewClaimExtraction,
  reviewGrounding,
  type GroundingContentRun,
  type GroundedClaim,
} from "@/lib/grounding-api";

function shortDigest(value?: string | null) {
  if (!value) return "—";
  return `${value.slice(0, 12)}…${value.slice(-8)}`;
}

function confidence(value: number) {
  return `${Math.round(value * 100)}%`;
}

function statusTone(status: string) {
  if (["GROUNDED", "SUPPORTED_INFERENCE", "OPINION", "PASS", "VERIFIED", "VERIFIED_COMPLETE"].includes(status)) return "green";
  if (["CONTRADICTED", "BLOCK", "REJECTED"].includes(status)) return "red";
  if (status === "INSUFFICIENT_EVIDENCE") return "amber";
  return "blue";
}

function ClaimCard({ claim }: { claim: GroundedClaim }) {
  return (
    <article style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 12, background: "var(--surface-active)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 7 }}>
        <span className={`premium-status premium-status--${statusTone(claim.grounding_status)}`}>{claim.grounding_status}</span>
        <span style={{ color: "var(--text-3)", fontSize: 11 }}>{claim.claim_type}</span>
        <span style={{ color: "var(--text-3)", fontSize: 11 }}>confidence {confidence(claim.confidence)}</span>
      </div>
      <p style={{ margin: 0, color: "var(--text-1)", lineHeight: 1.5 }}>{claim.statement}</p>
      {claim.source_refs.length > 0 && (
        <p style={{ margin: "8px 0 0", color: "var(--text-3)", fontSize: 11, fontFamily: "monospace" }}>
          evidence · {claim.source_refs.join(", ")}
        </p>
      )}
      {claim.rationale && <p style={{ margin: "8px 0 0", color: "var(--text-2)", fontSize: 12 }}>{claim.rationale}</p>}
    </article>
  );
}

export default function ReviewCockpitPage() {
  const params = useParams<{ run_id: string }>();
  const runId = decodeURIComponent(params.run_id);
  const [run, setRun] = useState<GroundingContentRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const value = await fetchContentRun(runId);
    setRun(value as GroundingContentRun);
  }, [runId]);

  useEffect(() => {
    let active = true;
    fetchContentRun(runId)
      .then((value) => { if (active) setRun(value as GroundingContentRun); })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [runId]);

  const execute = useCallback(async (label: string, action: () => Promise<unknown>, success: string) => {
    setBusy(label);
    setMessage(null);
    setError(null);
    try {
      await action();
      await refresh();
      setMessage(success);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review operation failed");
    } finally {
      setBusy(null);
    }
  }, [refresh]);

  const extractionVerified = run?.claim_extraction_review?.decision === "VERIFIED_COMPLETE";
  const gatePass = run?.grounding_gate?.decision === "PASS";
  const groundingVerified = run?.grounding_review?.decision === "VERIFIED";
  const extractionCurrent = Boolean(run?.claim_extraction && run?.final_content && run.claim_extraction.content_sha256);
  const visualUrl = resolveBackendAssetUrl(run?.visual_render?.asset_url);

  const progress = useMemo(() => {
    if (!run) return 0;
    let value = 0;
    if (run.claim_extraction) value += 1;
    if (extractionVerified) value += 1;
    if (run.grounding_assessment && run.grounding_gate) value += 1;
    if (groundingVerified) value += 1;
    return value;
  }, [extractionVerified, groundingVerified, run]);

  if (loading) {
    return <main className="premium-page"><div className="premium-container"><div className="premium-empty"><div><h3>Loading trust cockpit</h3><p>Reading the exact review revision.</p></div></div></div></main>;
  }
  if (!run) {
    return <main className="premium-page"><div className="premium-container"><Link href="/review">← Review center</Link><div className="premium-empty"><div><h3>ContentRun unavailable</h3><p>{error ?? "The requested review run could not be loaded."}</p></div></div></div></main>;
  }

  const reviewable = run.status === "READY_FOR_REVIEW";

  return (
    <main className="premium-page">
      <div className="premium-container">
        <header style={{ marginBottom: 24 }}>
          <Link href="/review" style={{ color: "var(--text-2)", textDecoration: "none", fontSize: 13 }}>← Human review center</Link>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 18, alignItems: "flex-start", marginTop: 14, flexWrap: "wrap" }}>
            <div style={{ maxWidth: 760 }}>
              <div className="premium-kicker">Trust cockpit · {progress}/4</div>
              <h1 className="premium-title" style={{ fontSize: 32 }}>{run.idea}</h1>
              <p className="premium-subtitle">{run.topic}</p>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
              <span className={`premium-status premium-status--${reviewable ? "purple" : "amber"}`}>{run.status.replaceAll("_", " ")}</span>
              <span className={`premium-status premium-status--${groundingVerified ? "green" : gatePass ? "amber" : run.grounding_gate?.decision === "BLOCK" ? "red" : "blue"}`}>
                {groundingVerified ? "TRUST VERIFIED" : gatePass ? "POLICY PASS · HUMAN PENDING" : run.grounding_gate?.decision === "BLOCK" ? "TRUST BLOCKED" : "TRUST NOT MEASURED"}
              </span>
            </div>
          </div>
        </header>

        {(error || message) && (
          <div style={{ marginBottom: 18, border: "1px solid var(--border)", borderRadius: 10, padding: 12, background: "var(--surface)", color: error ? "#ffb4b4" : "var(--text-2)" }}>
            {error ?? message}
          </div>
        )}

        {!reviewable && (
          <section className="premium-panel" style={{ marginBottom: 18 }}>
            <div className="premium-panel__body">
              This cockpit is read-only because the run is no longer READY_FOR_REVIEW. Trust material below remains inspectable.
            </div>
          </section>
        )}

        <section style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.35fr) minmax(300px, .65fr)", gap: 18, marginBottom: 18 }}>
          <article className="premium-panel">
            <header className="premium-panel__header"><div><h2>Exact final content</h2><p>The claim map below must describe this exact revision.</p></div></header>
            <div className="premium-panel__body">
              <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.65, color: "var(--text-1)" }}>{run.final_content || "No final content"}</div>
            </div>
          </article>

          <div style={{ display: "grid", gap: 18, alignContent: "start" }}>
            <article className="premium-panel">
              <header className="premium-panel__header"><div><h2>Evidence boundary</h2><p>Server-owned generation provenance.</p></div></header>
              <div className="premium-panel__body">
                {run.generation_source_packet ? (
                  <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "auto 1fr", gap: "7px 10px", fontSize: 12 }}>
                    <dt style={{ color: "var(--text-3)" }}>Packet</dt><dd style={{ margin: 0 }}>{run.generation_source_packet.title}</dd>
                    <dt style={{ color: "var(--text-3)" }}>ID</dt><dd style={{ margin: 0, fontFamily: "monospace" }}>{run.generation_source_packet.packet_id}</dd>
                    <dt style={{ color: "var(--text-3)" }}>Strict</dt><dd style={{ margin: 0 }}>{run.generation_source_packet.strict_mode ? "yes" : "no"}</dd>
                  </dl>
                ) : <p style={{ margin: 0, color: "var(--text-2)" }}>No immutable generation SourcePacket is bound to this run. The current-evidence cockpit will fail closed.</p>}
              </div>
            </article>

            <article className="premium-panel">
              <header className="premium-panel__header"><div><h2>Final visual</h2><p>Editorial wheel HP includes the actual asset.</p></div></header>
              <div className="premium-panel__body">
                {visualUrl && run.visual_render?.status === "READY" ? (
                  <>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={visualUrl} alt="Current final visual" style={{ width: "100%", display: "block", borderRadius: 8, border: "1px solid var(--border)" }} />
                    <p style={{ margin: "9px 0 0", color: "var(--text-3)", fontSize: 11 }}>provider · {run.visual_render.provider}<br />asset · {shortDigest(run.visual_render.asset_sha256)}</p>
                  </>
                ) : <p style={{ margin: 0, color: "var(--text-2)" }}>No current READY visual. The content dyno will expose this as drivetrain loss.</p>}
              </div>
            </article>
          </div>
        </section>

        <section className="premium-panel" style={{ marginBottom: 18 }}>
          <header className="premium-panel__header">
            <div><div className="premium-kicker">Step 1</div><h2>Extract factual claims</h2><p>The model proposes exact spans and semantic types. It cannot declare extraction completeness or Grounding status.</p></div>
            <button className="premium-button-secondary" disabled={!reviewable || Boolean(busy)} onClick={() => execute("extract", () => extractClaims(run.run_id), "Fresh claim extraction persisted. Review every claim before marking it complete.")}>
              {busy === "extract" ? "Extracting…" : run.claim_extraction ? "Re-extract claims" : "Extract claims"}
            </button>
          </header>
          <div className="premium-panel__body">
            {!run.claim_extraction ? <p style={{ margin: 0, color: "var(--text-2)" }}>No claim extraction exists for this revision.</p> : (
              <div style={{ display: "grid", gap: 10 }}>
                <div style={{ color: "var(--text-3)", fontSize: 11 }}>extractor · {run.claim_extraction.extractor_version} · {run.claim_extraction.claims.length} proposed claim(s) · content {shortDigest(run.claim_extraction.content_sha256)}</div>
                {run.claim_extraction.claims.map((claim) => (
                  <article key={claim.claim_id} style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 12, background: "var(--surface-active)" }}>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 6 }}><span className="premium-status premium-status--blue">{claim.claim_type}</span><span style={{ color: "var(--text-3)", fontSize: 11 }}>confidence {confidence(claim.confidence)}</span>{claim.text_start != null && claim.text_end != null && <span style={{ color: "var(--text-3)", fontSize: 11 }}>span {claim.text_start}:{claim.text_end}</span>}</div>
                    <p style={{ margin: 0, lineHeight: 1.5 }}>{claim.statement}</p>
                  </article>
                ))}
                {run.claim_extraction.claims.length === 0 && <p style={{ margin: 0, color: "#ffcf86" }}>The extractor returned zero claims. Strict Grounding will still block an empty assessment; do not mark completeness just to advance the workflow.</p>}
              </div>
            )}
          </div>
        </section>

        <section className="premium-panel" style={{ marginBottom: 18 }}>
          <header className="premium-panel__header">
            <div><div className="premium-kicker">Step 2 · Human authority</div><h2>Verify extraction completeness</h2><p>Confirm that the proposed map did not omit any factual, experiential, causal, numerical, predictive, or inferential claim in the exact final content.</p></div>
          </header>
          <div className="premium-panel__body">
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              <button className="premium-button" disabled={!reviewable || !extractionCurrent || Boolean(busy)} onClick={() => execute("complete", () => reviewClaimExtraction(run.run_id, "VERIFIED_COMPLETE"), "You explicitly marked this exact claim extraction VERIFIED_COMPLETE.")}>
                {busy === "complete" ? "Saving…" : "I reviewed every claim · complete"}
              </button>
              <button className="premium-button-secondary" disabled={!reviewable || !run.claim_extraction || Boolean(busy)} onClick={() => execute("reject-extraction", () => reviewClaimExtraction(run.run_id, "REJECTED"), "Extraction rejected. Re-extract or revise the content before semantic Grounding.")}>
                Reject extraction
              </button>
              {run.claim_extraction_review && <span className={`premium-status premium-status--${statusTone(run.claim_extraction_review.decision)}`}>{run.claim_extraction_review.decision}</span>}
            </div>
          </div>
        </section>

        <section className="premium-panel" style={{ marginBottom: 18 }}>
          <header className="premium-panel__header">
            <div><div className="premium-kicker">Step 3 · Server authority</div><h2>Match evidence and derive Grounding</h2><p>The browser sends no evidence packet and no semantic relations. The server reloads the immutable generation packet, invokes the proposal-only matcher, freezes the draft, then derives Grounding deterministically.</p></div>
            <button className="premium-button-secondary" disabled={!reviewable || !extractionVerified || !run.generation_source_packet || Boolean(busy)} onClick={() => execute("match", () => matchAndEvaluateCurrentEvidence(run.run_id), "Semantic proposals evaluated. Inspect every Grounding status before human verification.")}>
              {busy === "match" ? "Matching…" : run.grounding_assessment ? "Re-run match + evaluation" : "Match + evaluate current evidence"}
            </button>
          </header>
          <div className="premium-panel__body">
            {!run.grounding_assessment || !run.grounding_gate ? <p style={{ margin: 0, color: "var(--text-2)" }}>No current Grounding assessment exists.</p> : (
              <div style={{ display: "grid", gap: 12 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <span className={`premium-status premium-status--${statusTone(run.grounding_gate.decision)}`}>POLICY {run.grounding_gate.decision}</span>
                  <span style={{ color: "var(--text-3)", fontSize: 11 }}>{run.grounding_gate.policy_version}</span>
                  <span style={{ color: "var(--text-3)", fontSize: 11 }}>{run.grounding_assessment.claims.length} assessed claim(s)</span>
                </div>
                {run.grounding_gate.reasons.length > 0 && (
                  <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 10, color: "var(--text-2)", fontSize: 12 }}>
                    {run.grounding_gate.reasons.map((reason) => <div key={reason}>• {reason}</div>)}
                  </div>
                )}
                {run.grounding_assessment.claims.map((claim) => <ClaimCard key={claim.claim_id} claim={claim} />)}
              </div>
            )}
          </div>
        </section>

        <section className="premium-panel" style={{ marginBottom: 28 }}>
          <header className="premium-panel__header">
            <div><div className="premium-kicker">Step 4 · Human authority</div><h2>Grounding verification</h2><p>Policy PASS is necessary but not publication authority. Inspect the claim/evidence map and explicitly verify or reject this exact revision.</p></div>
          </header>
          <div className="premium-panel__body">
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              <button className="premium-button" disabled={!reviewable || !gatePass || Boolean(busy)} onClick={() => execute("verify-grounding", () => reviewGrounding(run.run_id, "VERIFIED"), "Grounding VERIFIED for this exact content/evidence/assessment revision.")}>
                {busy === "verify-grounding" ? "Verifying…" : "Verify Grounding"}
              </button>
              <button className="premium-button-secondary" disabled={!reviewable || !run.grounding_assessment || Boolean(busy)} onClick={() => execute("reject-grounding", () => reviewGrounding(run.run_id, "REJECTED"), "Grounding rejected. Approval remains blocked.")}>
                Reject Grounding
              </button>
              {run.grounding_review && <span className={`premium-status premium-status--${statusTone(run.grounding_review.decision)}`}>{run.grounding_review.decision}</span>}
            </div>
            {run.grounding_gate?.decision === "BLOCK" && <p style={{ margin: "12px 0 0", color: "#ffb4b4" }}>Verification is intentionally disabled while deterministic policy is BLOCK. Remediate or revise, then run a fresh extraction + Grounding cycle.</p>}
          </div>
        </section>

        {groundingVerified && (
          <section style={{ border: "1px solid var(--border-active)", borderRadius: 12, background: "var(--surface)", padding: 20, display: "flex", justifyContent: "space-between", gap: 18, alignItems: "center", flexWrap: "wrap" }}>
            <div><div className="premium-kicker">Trust boundary complete</div><h2 style={{ margin: "5px 0 6px" }}>This exact revision is ready for the separate approval decision.</h2><p style={{ margin: 0, color: "var(--text-2)" }}>Grounding verification does not publish and does not approve. Publication authority remains downstream.</p></div>
            <Link href={`/library/${encodeURIComponent(run.run_id)}`} className="premium-button">Open approval bundle</Link>
          </section>
        )}
      </div>
    </main>
  );
}
