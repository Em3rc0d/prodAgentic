"use client";

import { useEffect, useMemo, useState } from "react";

import { PremiumScene } from "@/components/PremiumScene";
import {
  ContentProfile,
  ContentProfileInput,
  createContentProfile,
  fetchContentProfiles,
  setDefaultContentProfile,
  updateContentProfile,
} from "@/lib/api";
import styles from "./profiles.module.css";

const EMPTY: ContentProfileInput = {
  name: "", display_name: "", positioning: "", audience: [], voice: [], core_topics: [], excluded_topics: [],
  target_language: "es", image_prompt_language: "en", min_words: 150, max_words: 220,
  preferred_style: "educational", visual_enabled: true, default_aspect_ratio: "16:9", default_visual_style: "",
  forbidden_claims: [], banned_phrases: [], brand_constraints: [], is_default: false,
};

function csv(value: string) { return value.split(",").map((item) => item.trim()).filter(Boolean); }
function csvText(value: string[]) { return value.join(", "); }

function editableProfile(profile: ContentProfile): ContentProfileInput {
  return {
    name: profile.name,
    display_name: profile.display_name ?? "",
    positioning: profile.positioning ?? "",
    audience: [...profile.audience],
    voice: [...profile.voice],
    core_topics: [...profile.core_topics],
    excluded_topics: [...profile.excluded_topics],
    target_language: profile.target_language,
    image_prompt_language: profile.image_prompt_language,
    min_words: profile.min_words,
    max_words: profile.max_words,
    preferred_style: profile.preferred_style,
    visual_enabled: profile.visual_enabled,
    default_aspect_ratio: profile.default_aspect_ratio,
    default_visual_style: profile.default_visual_style,
    forbidden_claims: [...profile.forbidden_claims],
    banned_phrases: [...profile.banned_phrases],
    brand_constraints: [...profile.brand_constraints],
    is_default: profile.is_default,
  };
}

function freshProfile(): ContentProfileInput {
  return { ...EMPTY, audience: [], voice: [], core_topics: [], excluded_topics: [], forbidden_claims: [], banned_phrases: [], brand_constraints: [] };
}

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<ContentProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState<ContentProfileInput>(freshProfile());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selected = useMemo(() => profiles.find((profile) => profile.profile_id === selectedId) ?? null, [profiles, selectedId]);
  const defaultProfile = useMemo(() => profiles.find((profile) => profile.is_default) ?? null, [profiles]);

  function selectProfile(profile: ContentProfile) {
    setSelectedId(profile.profile_id);
    setForm(editableProfile(profile));
    setMessage(null);
    setError(null);
  }

  async function reload(preferredId?: string) {
    const result = await fetchContentProfiles();
    setProfiles(result.profiles);
    if (preferredId) {
      const preferred = result.profiles.find((profile) => profile.profile_id === preferredId);
      if (preferred) {
        setSelectedId(preferred.profile_id);
        setForm(editableProfile(preferred));
      }
    }
  }

  useEffect(() => {
    fetchContentProfiles()
      .then((result) => setProfiles(result.profiles))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  function newProfile() {
    setSelectedId(null);
    setForm(freshProfile());
    setMessage(null);
    setError(null);
  }

  async function save() {
    if (!form.name.trim()) return;
    setSaving(true); setMessage(null); setError(null);
    try {
      if (selectedId) {
        const updated = await updateContentProfile(selectedId, form);
        await reload(updated.profile_id);
        setMessage(`Saved profile v${updated.version}`);
      } else {
        const created = await createContentProfile(form);
        await reload(created.profile_id);
        setMessage("Profile created");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Profile save failed");
    } finally { setSaving(false); }
  }

  async function makeDefault(profileId: string) {
    setSaving(true); setMessage(null); setError(null);
    try {
      await setDefaultContentProfile(profileId);
      await reload(profileId);
      setMessage("Default generation profile updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set default profile");
    } finally { setSaving(false); }
  }

  return (
    <main className="premium-page">
      <div className="premium-container">
        <section className="premium-hero">
          <div>
            <div className="premium-kicker">Identity architecture</div>
            <h1 className="premium-title">Content profiles</h1>
            <p className="premium-subtitle">Define reusable identity, audience, voice and guardrails. Every new ContentRun receives a versioned snapshot so future edits never rewrite past evidence.</p>
            <div className="premium-actions">
              <button className="premium-button" onClick={newProfile}>New profile</button>
              <span className="premium-status premium-status--purple">{profiles.length} profiles</span>
            </div>
          </div>
          <PremiumScene variant="profiles" />
        </section>

        <section className="premium-metrics" aria-label="Profile summary">
          <div className="premium-metric"><span className="premium-metric__label">Profiles</span><strong className="premium-metric__value">{profiles.length}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Default</span><strong className="premium-metric__value" style={{ fontSize: 15, marginTop: 13 }}>{defaultProfile?.display_name || defaultProfile?.name || "—"}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Target language</span><strong className="premium-metric__value">{(selected?.target_language || defaultProfile?.target_language || "—").toUpperCase()}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Visual policy</span><strong className="premium-metric__value" style={{ fontSize: 15, marginTop: 13 }}>{form.visual_enabled ? "Enabled" : "Disabled"}</strong></div>
        </section>

        <div className={styles.workspace}>
          <aside className="premium-panel">
            <header className="premium-panel__header"><div><h2>Profile vault</h2><p>Reusable publishing identities</p></div></header>
            <div className={styles.profileList}>
              {loading && <div className="premium-empty" style={{ minHeight: 150 }}><div><p>Loading profiles…</p></div></div>}
              {!loading && profiles.length === 0 && <div className="premium-empty" style={{ minHeight: 170 }}><div><div className="premium-empty__icon">◎</div><h3>No profiles yet</h3><p>Create the first reusable identity contract.</p></div></div>}
              {profiles.map((profile) => (
                <button key={profile.profile_id} onClick={() => selectProfile(profile)} className={`${styles.profileButton}${selectedId === profile.profile_id ? ` ${styles.profileButtonActive}` : ""}`}>
                  <span className={styles.profileName}>{profile.display_name || profile.name}</span>
                  {profile.is_default && <span className={styles.defaultBadge}>DEFAULT</span>}
                  <span className={styles.profileMeta}>v{profile.version} · {profile.target_language.toUpperCase()} · {profile.preferred_style}</span>
                </button>
              ))}
            </div>
          </aside>

          <section className={`premium-panel ${styles.editor}`}>
            <header className="premium-panel__header">
              <div><h2>{selected ? `Edit ${selected.display_name || selected.name}` : "Create profile"}</h2><p>Existing ContentRuns preserve their original profile snapshot.</p></div>
              {selected && !selected.is_default && <button className="premium-button-secondary" disabled={saving} onClick={() => makeDefault(selected.profile_id)}>Set as default</button>}
            </header>

            <div className={`premium-panel__body ${styles.formGrid}`}>
              <section className={styles.section}>
                <div className={styles.sectionHeader}><h3>Identity</h3><p>The public-facing professional context that shapes every generation.</p></div>
                <label className="premium-label">Internal name<input className="premium-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
                <label className="premium-label">Public display name<input className="premium-input" value={form.display_name ?? ""} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></label>
                <label className={`premium-label ${styles.full}`}>Positioning<textarea className="premium-textarea" value={form.positioning ?? ""} onChange={(e) => setForm({ ...form, positioning: e.target.value })} /></label>
              </section>

              <section className={styles.section}>
                <div className={styles.sectionHeader}><h3>Audience & voice</h3><p>Who the content serves and how the profile should sound.</p></div>
                <label className="premium-label">Audience<input className="premium-input" value={csvText(form.audience)} onChange={(e) => setForm({ ...form, audience: csv(e.target.value) })} placeholder="architects, CTOs, AI builders" /></label>
                <label className="premium-label">Voice<input className="premium-input" value={csvText(form.voice)} onChange={(e) => setForm({ ...form, voice: csv(e.target.value) })} placeholder="technical, concise, conversational" /></label>
                <label className="premium-label">Core topics<input className="premium-input" value={csvText(form.core_topics)} onChange={(e) => setForm({ ...form, core_topics: csv(e.target.value) })} /></label>
                <label className="premium-label">Excluded topics<input className="premium-input" value={csvText(form.excluded_topics)} onChange={(e) => setForm({ ...form, excluded_topics: csv(e.target.value) })} /></label>
              </section>

              <section className={styles.section}>
                <div className={styles.sectionHeader}><h3>Guardrails</h3><p>Hard boundaries for claims, phrasing and brand behavior.</p></div>
                <label className="premium-label">Forbidden claims<input className="premium-input" value={csvText(form.forbidden_claims)} onChange={(e) => setForm({ ...form, forbidden_claims: csv(e.target.value) })} /></label>
                <label className="premium-label">Banned phrases<input className="premium-input" value={csvText(form.banned_phrases)} onChange={(e) => setForm({ ...form, banned_phrases: csv(e.target.value) })} /></label>
                <label className={`premium-label ${styles.full}`}>Brand constraints<input className="premium-input" value={csvText(form.brand_constraints)} onChange={(e) => setForm({ ...form, brand_constraints: csv(e.target.value) })} /></label>
              </section>

              <section className={styles.section}>
                <div className={styles.sectionHeader}><h3>Generation & visual defaults</h3><p>Reusable defaults for language, length and visual output.</p></div>
                <label className="premium-label">Target language<select className="premium-select" value={form.target_language} onChange={(e) => setForm({ ...form, target_language: e.target.value as ContentProfileInput["target_language"] })}><option value="es">Español</option><option value="en">English</option><option value="pt">Português</option></select></label>
                <label className="premium-label">Image prompt language<select className="premium-select" value={form.image_prompt_language} onChange={(e) => setForm({ ...form, image_prompt_language: e.target.value as ContentProfileInput["image_prompt_language"] })}><option value="en">English</option><option value="es">Español</option><option value="pt">Português</option></select></label>
                <label className="premium-label">Min words<input className="premium-input" type="number" value={form.min_words} onChange={(e) => setForm({ ...form, min_words: Number(e.target.value) })} /></label>
                <label className="premium-label">Max words<input className="premium-input" type="number" value={form.max_words} onChange={(e) => setForm({ ...form, max_words: Number(e.target.value) })} /></label>
                <label className="premium-label">Default ratio<select className="premium-select" value={form.default_aspect_ratio} onChange={(e) => setForm({ ...form, default_aspect_ratio: e.target.value as ContentProfileInput["default_aspect_ratio"] })}><option value="16:9">16:9</option><option value="1:1">1:1</option><option value="4:5">4:5</option></select></label>
                <label className="premium-label">Default visual style<select className="premium-select" value={form.default_visual_style} onChange={(e) => setForm({ ...form, default_visual_style: e.target.value })}><option value="">Default</option><option value="technical_editorial">Technical Editorial</option><option value="cinematic">Cinematic</option><option value="minimal">Minimal</option><option value="illustration">Illustration</option><option value="photorealistic">Photorealistic</option></select></label>
                <label className={styles.checkbox}><input type="checkbox" checked={form.visual_enabled} onChange={(e) => setForm({ ...form, visual_enabled: e.target.checked })} />Generate visual prompts for this profile</label>
              </section>
            </div>

            <footer className={styles.footer}>
              <div>{error && <span className={styles.error}>{error}</span>}{message && <span className={styles.message}>{message}</span>}</div>
              <button className="premium-button" disabled={saving || !form.name.trim() || form.min_words > form.max_words} onClick={save}>{saving ? "Saving…" : selected ? "Save profile" : "Create profile"}</button>
            </footer>
          </section>
        </div>
      </div>
    </main>
  );
}
