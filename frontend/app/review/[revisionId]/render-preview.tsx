"use client";

import { useEffect, useState } from "react";
import { fetchRenderPreview, fetchRevisionQAEvidence, type RenderPreviewV1, type RevisionQAEvidenceV1 } from "../../../lib/rendering";
import { approveRevision, downloadManualExport, editRevision, fetchReviewAuthority, type ApprovalBundleV2, type ReviewAuthoritySnapshotV1 } from "../../../lib/approval";
import { fetchProductionRevision, type ProductionRevisionSnapshot } from "../../../lib/r2-production";
import styles from "./review.module.css";

type ReviewContent = ReviewAuthoritySnapshotV1["content"] | ProductionRevisionSnapshot["content"]["payload"];

export default function RenderPreview({ revisionId }: { revisionId: string }) {
  const [preview, setPreview] = useState<RenderPreviewV1 | null>(null);
  const [revision, setRevision] = useState<ProductionRevisionSnapshot | null>(null);
  const [qa, setQa] = useState<RevisionQAEvidenceV1 | null>(null);
  const [authority, setAuthority] = useState<ReviewAuthoritySnapshotV1 | null>(null);
  const [approval, setApproval] = useState<ApprovalBundleV2 | null>(null);
  const [activePage, setActivePage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [qaError, setQaError] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editedBody, setEditedBody] = useState("");
  const [forkedRevisionId, setForkedRevisionId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [revisionResult, previewResult, qaResult, authorityResult] = await Promise.allSettled([
        fetchProductionRevision(revisionId),
        fetchRenderPreview(revisionId),
        fetchRevisionQAEvidence(revisionId),
        fetchReviewAuthority(revisionId),
      ]);
      if (cancelled) return;

      const revisionValue = revisionResult.status === "fulfilled" ? revisionResult.value : null;
      const previewValue = previewResult.status === "fulfilled" ? previewResult.value : null;
      const authorityValue = authorityResult.status === "fulfilled" ? authorityResult.value : null;

      if (revisionValue) setRevision(revisionValue);
      if (previewValue) {
        setPreview(previewValue);
        setActivePage(0);
      }
      if (qaResult.status === "fulfilled") setQa(qaResult.value);
      else setQaError(true);
      if (authorityValue) {
        setAuthority(authorityValue);
        setEditedBody(String(authorityValue.content.body || ""));
      }

      const knownFormat = authorityValue?.content.format ?? revisionValue?.content.payload.format ?? previewValue?.format ?? null;
      const hasUsableAuthority = Boolean(authorityValue || revisionValue || previewValue);
      const needsRender = knownFormat !== null && knownFormat !== "text";
      if (!hasUsableAuthority) {
        setError("Revision authority and rendered preview are unavailable.");
      } else if (needsRender && !previewValue) {
        setError("Rendered preview is unavailable for this visual revision.");
      }
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [revisionId]);

  async function onApprove() {
    if (!authority || !authority.approval_available || actionBusy) return;
    setActionBusy(true);
    setActionError(null);
    try {
      const frozen = await approveRevision(revisionId, authority.review_digest);
      setApproval(frozen);
      setAuthority({ ...authority, approval_available: false, existing_approval_id: frozen.approval_id });
      setEditing(false);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "Approval failed");
    } finally {
      setActionBusy(false);
    }
  }

  async function onSaveEdit() {
    if (!authority || actionBusy) return;
    const body = editedBody.trim();
    if (!body) {
      setActionError("Caption/body cannot be blank.");
      return;
    }
    setActionBusy(true);
    setActionError(null);
    try {
      const editedContent = { ...authority.content, content_spec_id: `human-edit-${crypto.randomUUID()}`, body };
      const result = await editRevision(revisionId, authority.review_digest, editedContent);
      setForkedRevisionId(result.revision.revision_id);
      setEditing(false);
      setAuthority({ ...authority, approval_available: false });
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "Edit failed");
    } finally {
      setActionBusy(false);
    }
  }

  async function onManualExport(approvalId: string) {
    if (actionBusy) return;
    setActionBusy(true);
    setActionError(null);
    try {
      await downloadManualExport(approvalId);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "Manual export failed");
    } finally {
      setActionBusy(false);
    }
  }

  if (loading) {
    return <main className={styles.shell}><section className={styles.stateCard}><p className={styles.eyebrow}>Review</p><h1>Loading exact revision…</h1></section></main>;
  }
  if (error) {
    return <main className={styles.shell}><section className={styles.stateCard}><p className={styles.eyebrow}>Review</p><h1>Preview unavailable</h1><p>{error}</p></section></main>;
  }

  const content: ReviewContent | null = authority?.content ?? revision?.content.payload ?? null;
  const format = content?.format ?? preview?.format ?? null;
  const textOnly = format === "text";
  const asset = preview?.assets[activePage];
  const revisionStatus = qa?.revision_status ?? revision?.revision.status ?? preview?.status ?? "QA_PENDING";
  const ready = qa?.readiness === "READY_FOR_REVIEW" || revisionStatus === "REVIEWABLE";
  const needsAttention = qa?.readiness === "NEEDS_ATTENTION";
  const approved = Boolean(approval || authority?.existing_approval_id);
  const manualExportEnabled = process.env.NEXT_PUBLIC_MK1_MANUAL_EXPORT === "true";
  const exportApprovalId = approval?.approval_id || authority?.existing_approval_id || null;
  const exportAvailable = approved && manualExportEnabled && Boolean(exportApprovalId);
  const statusLabel = approved ? "Approved · package frozen" : ready ? "Ready for review" : needsAttention ? "QA · needs attention" : textOnly ? "Text · QA pending" : "Rendered · QA pending";
  const headerTitle = content?.title ? String(content.title) : textOnly ? "Text post" : "Rendered visual";
  const detailFormat = format ? String(format).replaceAll("_", " ") : "unknown";

  return <main className={styles.shell} data-testid="s5-review-preview" data-qa-readiness={qa?.readiness || (ready ? "READY_FOR_REVIEW" : "QA_PENDING")} data-s7-approval={approved ? "APPROVED" : authority?.approval_available ? "AVAILABLE" : "UNAVAILABLE"} data-s8-export={exportAvailable ? "AVAILABLE" : "UNAVAILABLE"}>
    <header className={styles.header}>
      <div>
        <p className={styles.eyebrow}>Review · governed decision</p>
        <h1>{headerTitle}</h1>
        <p className={styles.subtle}>{approved ? "Approved · exact content package frozen. Any change now creates a new revision and a new approval path." : ready ? "QA is complete. Review the content itself; evidence and lineage remain available under details." : needsAttention ? "QA found a blocking issue. Valid upstream work is preserved while recovery resolves the broken layer." : textOnly ? "Text-only content correctly bypassed VisualSpec and Renderer. QA authority still gates Review." : "The owned render bytes are awaiting QA. Approval is intentionally unavailable."}</p>
      </div>
      <div className={styles.status} aria-label={statusLabel}><span className={styles.dot} aria-hidden="true" />{statusLabel}</div>
    </header>

    <section className={`${styles.workspace} ${textOnly ? styles.textWorkspace : ""}`}>
      {!textOnly && <aside className={styles.rail} aria-label="Rendered pages">{preview?.assets.map((item, index) => <button key={item.asset_id} type="button" className={`${styles.thumbButton} ${index === activePage ? styles.active : ""}`} onClick={() => setActivePage(index)} aria-current={index === activePage ? "page" : undefined} aria-label={`Show rendered page ${index + 1} of ${preview.assets.length}`}><img src={item.url} alt="" className={styles.thumb} /><span>{index + 1}</span></button>)}</aside>}

      <div className={styles.previewStage}>
        {textOnly && content ? <article className={styles.textPreview} aria-label="Text content preview"><span>TEXT</span><h2>{String(content.hook || "")}</h2><p>{String(content.body || "")}</p>{content.cta && <strong>{String(content.cta)}</strong>}</article> : asset ? <figure className={styles.figure}><img src={asset.url} alt={preview?.alt_text || `Rendered ${preview?.format} page ${activePage + 1}`} className={styles.heroImage} width={asset.width} height={asset.height} /><figcaption>Page {activePage + 1} of {preview?.assets.length} · {asset.width}×{asset.height}</figcaption></figure> : <p>No rendered pages found.</p>}
      </div>

      <aside className={styles.details}>
        {authority && <section className={styles.copyPanel} aria-label="Review copy"><p className={styles.eyebrow}>Copy</p><h2>{String(authority.content.hook || "")}</h2>{editing ? <textarea aria-label="Caption or body" className={styles.editor} value={editedBody} onChange={(event) => setEditedBody(event.target.value)} rows={9} /> : <p className={styles.caption}>{String(authority.content.body || "")}</p>}{authority.content.cta && <p className={styles.cta}>{String(authority.content.cta)}</p>}</section>}
        <div className={styles.actions} aria-label="Review actions">
          {authority?.approval_available && !approved && !editing && <button className={styles.primaryAction} type="button" onClick={onApprove} disabled={actionBusy}>{actionBusy ? "Approving…" : "Approve"}</button>}
          {exportAvailable && exportApprovalId && !editing && <button className={styles.primaryAction} type="button" onClick={() => onManualExport(exportApprovalId)} disabled={actionBusy}>{actionBusy ? "Preparing package…" : "Download manual package"}</button>}
          {authority && !editing && !forkedRevisionId && <button className={styles.secondaryAction} type="button" onClick={() => setEditing(true)} disabled={actionBusy}>{approved ? "Create revision" : "Edit"}</button>}
          {editing && <><button className={styles.primaryAction} type="button" onClick={onSaveEdit} disabled={actionBusy}>Save as new revision</button><button className={styles.secondaryAction} type="button" onClick={() => setEditing(false)} disabled={actionBusy}>Cancel</button></>}
        </div>
        {approval && <div className={styles.approvedReceipt} data-testid="s7-approved-receipt"><strong>Approved · exact content package frozen</strong><span>{approval.approval_id}</span><code>{approval.bundle_sha256}</code></div>}
        {forkedRevisionId && <div className={styles.approvedReceipt} data-testid="s7-edit-receipt"><strong>New revision created</strong><a href={`/review/${encodeURIComponent(forkedRevisionId)}`}>Open {forkedRevisionId}</a></div>}
        {actionError && <p role="alert" className={styles.actionError}>{actionError}</p>}
        <details className={styles.whyDetails}>
          <summary>Why / Details</summary>
          <dl>
            <div><dt>Revision</dt><dd>{revision?.revision.revision_id ?? preview?.revision_id ?? authority?.revision_id ?? revisionId}</dd></div>
            <div><dt>Format</dt><dd>{detailFormat}</dd></div>
            <div><dt>State</dt><dd>{qa?.readiness || revisionStatus}</dd></div>
            {qa?.qa_report && <div><dt>QA verdict</dt><dd>{qa.qa_report.verdict.replaceAll("_", " ")}</dd></div>}
            {asset && <div><dt>Asset SHA-256</dt><dd className={styles.digest}>{asset.sha256}</dd></div>}
            {authority && <div><dt>Review digest</dt><dd className={styles.digest}>{authority.review_digest}</dd></div>}
          </dl>
          {qa?.qa_report && <div className={styles.qaEvidence}><strong>QA evidence</strong><div><span>Report</span><span>{qa.qa_report.qa_report_id}</span></div><div><span>Recovery attempt</span><span>{qa.qa_report.recovery_attempt}</span></div><div><span>Warnings</span><span>{qa.qa_report.warnings.length}</span></div><div><span>Blocking failures</span><span>{qa.qa_report.failures.length}</span></div><div><span>Digest</span><span className={styles.digest}>{qa.qa_report.digest}</span></div></div>}
        </details>
        <div className={styles.notice}>{qaError ? "QA evidence is temporarily unavailable; Review does not infer readiness from presentation alone." : exportAvailable ? "Manual package uses this exact Approval and re-verifies owned asset bytes before download. Scheduling and publication remain separate." : authority ? "Approve freezes this exact revision, QA evidence and owned asset hashes. Edit always creates a new revision." : ready ? "S6 has made this revision reviewable. S7 approval authority is unavailable or disabled." : "S6 must complete QA before this revision can become reviewable."}</div>
      </aside>
    </section>
  </main>;
}
