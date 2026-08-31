"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import {
  ACTIVE_SOURCE_PACKET_STORAGE_KEY,
  createQuickSourcePacket,
  fetchSourcePackets,
  type SourcePacketSummary,
} from "@/lib/api";
import styles from "./EvidenceBriefDock.module.css";


function toSummary(packet: {
  packet_id: string;
  title: string;
  summary?: string | null;
  strict_mode: boolean;
  evidence: unknown[];
  allowed_facts: unknown[];
  allowed_inferences: unknown[];
  created_at: string;
}): SourcePacketSummary {
  return {
    packet_id: packet.packet_id,
    title: packet.title,
    summary: packet.summary,
    strict_mode: packet.strict_mode,
    evidence_count: packet.evidence.length,
    allowed_fact_count: packet.allowed_facts.length,
    allowed_inference_count: packet.allowed_inferences.length,
    created_at: packet.created_at,
  };
}


export function EvidenceBriefDock() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [packets, setPackets] = useState<SourcePacketSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [quickFacts, setQuickFacts] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (pathname !== "/") return;

    const stored = window.sessionStorage.getItem(ACTIVE_SOURCE_PACKET_STORAGE_KEY) || "";
    setSelectedId(stored);
    setLoading(true);
    fetchSourcePackets()
      .then((result) => setPackets(result.packets))
      .catch(() => setPackets([]))
      .finally(() => setLoading(false));
  }, [pathname]);

  const selected = useMemo(
    () => packets.find((packet) => packet.packet_id === selectedId) ?? null,
    [packets, selectedId],
  );

  if (pathname !== "/") return null;

  function selectPacket(packetId: string) {
    setSelectedId(packetId);
    setError(null);
    if (packetId) {
      window.sessionStorage.setItem(ACTIVE_SOURCE_PACKET_STORAGE_KEY, packetId);
    } else {
      window.sessionStorage.removeItem(ACTIVE_SOURCE_PACKET_STORAGE_KEY);
    }
  }

  async function saveQuickFacts() {
    const facts = quickFacts
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    if (facts.length === 0) {
      setError("Add at least one factual statement, one per line.");
      return;
    }
    if (facts.length > 25) {
      setError("Quick evidence supports at most 25 factual statements per packet.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const packet = await createQuickSourcePacket({
        title: `Create Studio evidence · ${new Date().toLocaleDateString()}`,
        summary: "Explicit user-provided factual statements captured from Create Studio.",
        facts,
      });
      const summary = toSummary(packet);
      setPackets((current) => [summary, ...current.filter((item) => item.packet_id !== summary.packet_id)]);
      setQuickFacts("");
      selectPacket(packet.packet_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the evidence packet.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.dock}>
      {open && (
        <section className={styles.panel} aria-label="Evidence boundary">
          <div className={styles.heading}>
            <div>
              <span>Evidence boundary</span>
              <strong>Ground the brief</strong>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close evidence panel">×</button>
          </div>

          <p className={styles.intro}>
            Attach one immutable SourcePacket to the next pipeline run. Packet metadata is listed here; evidence excerpts stay behind the server boundary.
          </p>

          <label className={styles.label} htmlFor="source-packet-select">Existing packet</label>
          <select
            id="source-packet-select"
            className={styles.select}
            value={selectedId}
            onChange={(event) => selectPacket(event.target.value)}
            disabled={loading || saving}
          >
            <option value="">No evidence packet</option>
            {packets.map((packet) => (
              <option key={packet.packet_id} value={packet.packet_id}>{packet.title}</option>
            ))}
          </select>

          {selected && (
            <div className={styles.packetMeta}>
              <strong>{selected.title}</strong>
              <span>{selected.allowed_fact_count} facts · {selected.allowed_inference_count} inferences · strict {selected.strict_mode ? "on" : "off"}</span>
              {selected.summary && <small>{selected.summary}</small>}
            </div>
          )}

          <div className={styles.divider}><span>or capture quick evidence</span></div>

          <label className={styles.label} htmlFor="quick-evidence-facts">User-provided factual statements</label>
          <textarea
            id="quick-evidence-facts"
            className={styles.textarea}
            value={quickFacts}
            onChange={(event) => setQuickFacts(event.target.value)}
            placeholder={"One factual statement per line.\nExample: CI #550 passed all four release jobs."}
            disabled={saving}
          />
          <small className={styles.note}>
            These are explicit user assertions, not facts independently verified by prodAgentic. Final Grounding still applies before approval.
          </small>

          {error && <div className={styles.error}>{error}</div>}

          <button type="button" className={styles.saveButton} onClick={saveQuickFacts} disabled={saving || !quickFacts.trim()}>
            {saving ? "Creating packet…" : "Create & use packet"}
          </button>
        </section>
      )}

      <button
        type="button"
        className={`${styles.trigger} ${selectedId ? styles.triggerActive : ""}`}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label="Configure evidence for Create Studio"
      >
        <span className={styles.dot} />
        <span>
          <small>Evidence</small>
          <strong>{selected ? selected.title : selectedId ? "Packet attached" : "Not attached"}</strong>
        </span>
      </button>
    </div>
  );
}
