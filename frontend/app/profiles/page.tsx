"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ContentProfile,
  ContentProfileInput,
  createContentProfile,
  fetchContentProfiles,
  setDefaultContentProfile,
  updateContentProfile,
} from "@/lib/api";

const EMPTY: ContentProfileInput = {
  name: "",
  display_name: "",
  positioning: "",
  audience: [],
  voice: [],
  core_topics: [],
  excluded_topics: [],
  target_language: "es",
  image_prompt_language: "en",
  min_words: 150,
  max_words: 220,
  preferred_style: "educational",
  visual_enabled: true,
  default_aspect_ratio: "16:9",
  default_visual_style: "",
  forbidden_claims: [],
  banned_phrases: [],
  brand_constraints: [],
  is_default: false,
};

function csv(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function csvText(value: string[]) {
  return value.join(", ");
}

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<ContentProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState<ContentProfileInput>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selected = useMemo(
    () => profiles.find((profile) => profile.profile_id === selectedId) ?? null,
    [profiles, selectedId]
  );

  async function reload(preferredId?: string) {
    const result = await fetchContentProfiles();
    setProfiles(result.profiles);
    if (preferredId) setSelectedId(preferredId);
  }

  useEffect(() => {
    fetchContentProfiles()
      .then((result) => setProfiles(result.profiles))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) return;
    const { profile_id: _profileId, version: _version, archived: _archived, created_at: _createdAt, updated_at: _updatedAt, ...editable } = selected;
    void _profileId; void _version; void _archived; void _createdAt; void _updatedAt;
    setForm(editable);
  }, [selected]);

  function newProfile() {
    setSelectedId(null);
    setForm({ ...EMPTY, audience: [], voice: [], core_topics: [], excluded_topics: [], forbidden_claims: [], banned_phrases: [], brand_constraints: [] });
    setMessage(null);
    setError(null);
  }

  async function save() {
    if (!form.name.trim()) return;
    setSaving(true);
    setMessage(null);
    setError(null);
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
    } finally {
      setSaving(false);
    }
  }

  async function makeDefault(profileId: string) {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      await setDefaultContentProfile(profileId);
      await reload(profileId);
      setMessage("Default generation profile updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set default profile");
    } finally {
      setSaving(false);
    }
  }

  const inputStyle = {
    width: "100%",
    border: "1px solid var(--border)",
    borderRadius: 8,
    background: "var(--surface-active)",
    color: "var(--text-1)",
    padding: "10px 12px",
    fontFamily: "inherit",
  } as const;

  return (
    <main style={{ height: "100vh", overflowY: "auto", background: "var(--bg-0)", color: "var(--text-1)", padding: "42px 24px 100px" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 18, marginBottom: 28 }}>
          <div>
            <p style={{ margin: 0, color: "var(--text-3)", letterSpacing: ".08em", fontSize: 12 }}>prodAgentic</p>
            <h1 style={{ margin: "6px 0 8px", fontSize: 32 }}>Content Profiles</h1>
            <p style={{ margin: 0, color: "var(--text-2)", maxWidth: 700 }}>
              Reusable identity, audience, voice and guardrail contracts. The active profile is snapshotted into every new ContentRun.
            </p>
          </div>
          <button onClick={newProfile} style={{ ...inputStyle, width: "auto", cursor: "pointer" }}>+ New profile</button>
        </header>

        {error && <div style={{ padding: 12, border: "1px solid var(--border)", borderRadius: 8, marginBottom: 16 }}>{error}</div>}
        {message && <div style={{ padding: 12, border: "1px solid var(--border-success)", borderRadius: 8, marginBottom: 16 }}>{message}</div>}

        <div style={{ display: "grid", gridTemplateColumns: "300px minmax(0,1fr)", gap: 18 }}>
          <aside style={{ border: "1px solid var(--border)", borderRadius: 12, background: "var(--surface)", padding: 12, alignSelf: "start" }}>
            {loading && <p style={{ color: "var(--text-2)" }}>Loading profiles…</p>}
            {!loading && profiles.length === 0 && <p style={{ color: "var(--text-2)", fontSize: 13 }}>No profiles yet. Create the first reusable identity.</p>}
            <div style={{ display: "grid", gap: 8 }}>
              {profiles.map((profile) => (
                <button
                  key={profile.profile_id}
                  onClick={() => setSelectedId(profile.profile_id)}
                  style={{
                    textAlign: "left",
                    border: "1px solid var(--border)",
                    borderRadius: 9,
                    padding: 12,
                    background: selectedId === profile.profile_id ? "var(--surface-active)" : "transparent",
                    color: "var(--text-1)",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <strong>{profile.display_name || profile.name}</strong>
                    {profile.is_default && <span style={{ fontSize: 10, color: "var(--success)" }}>DEFAULT</span>}
                  </div>
                  <div style={{ marginTop: 5, color: "var(--text-3)", fontSize: 11 }}>v{profile.version} · {profile.target_language.toUpperCase()}</div>
                </button>
              ))}
            </div>
          </aside>

          <section style={{ border: "1px solid var(--border)", borderRadius: 12, background: "var(--surface)", padding: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 20 }}>{selected ? "Edit profile" : "Create profile"}</h2>
                <p style={{ margin: "5px 0 0", color: "var(--text-3)", fontSize: 12 }}>Existing ContentRuns keep their original snapshot after future edits.</p>
              </div>
              {selected && !selected.is_default && (
                <button disabled={saving} onClick={() => makeDefault(selected.profile_id)} style={{ ...inputStyle, width: "auto", cursor: "pointer" }}>Set as default</button>
              )}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={{ ...inputStyle, marginTop: 6 }} /></label>
              <label>Public display name<input value={form.display_name ?? ""} onChange={(e) => setForm({ ...form, display_name: e.target.value })} style={{ ...inputStyle, marginTop: 6 }} /></label>
              <label style={{ gridColumn: "1 / -1" }}>Positioning<textarea value={form.positioning ?? ""} onChange={(e) => setForm({ ...form, positioning: e.target.value })} style={{ ...inputStyle, marginTop: 6, minHeight: 80, resize: "vertical" }} /></label>
              <label>Audience<input value={csvText(form.audience)} onChange={(e) => setForm({ ...form, audience: csv(e.target.value) })} placeholder="architects, CTOs, AI builders" style={{ ...inputStyle, marginTop: 6 }} /></label>
              <label>Voice<input value={csvText(form.voice)} onChange={(e) => setForm({ ...form, voice: csv(e.target.value) })} placeholder="technical, concise, conversational" style={{ ...inputStyle, marginTop: 6 }} /></label>
              <label>Core topics<input value={csvText(form.core_topics)} onChange={(e) => setForm({ ...form, core_topics: csv(e.target.value) })} style={{ ...inputStyle, marginTop: 6 }} /></label>
              <label>Excluded topics<input value={csvText(form.excluded_topics)} onChange={(e) => setForm({ ...form, excluded_topics: csv(e.target.value) })} style={{ ...inputStyle, marginTop: 6 }} /></label>
              <label>Forbidden claims<input value={csvText(form.forbidden_claims)} onChange={(e) => setForm({ ...form, forbidden_claims: csv(e.target.value) })} style={{ ...inputStyle, marginTop: 6 }} /></label>
              <label>Banned phrases<input value={csvText(form.banned_phrases)} onChange={(e) => setForm({ ...form, banned_phrases: csv(e.target.value) })} style={{ ...inputStyle, marginTop: 6 }} /></label>
              <label style={{ gridColumn: "1 / -1" }}>Brand constraints<input value={csvText(form.brand_constraints)} onChange={(e) => setForm({ ...form, brand_constraints: csv(e.target.value) })} style={{ ...inputStyle, marginTop: 6 }} /></label>
              <label>Target language<select value={form.target_language} onChange={(e) => setForm({ ...form, target_language: e.target.value as ContentProfileInput["target_language"] })} style={{ ...inputStyle, marginTop: 6 }}><option value="es">Español</option><option value="en">English</option><option value="pt">Português</option></select></label>
              <label>Image prompt language<select value={form.image_prompt_language} onChange={(e) => setForm({ ...form, image_prompt_language: e.target.value as ContentProfileInput["image_prompt_language"] })} style={{ ...inputStyle, marginTop: 6 }}><option value="en">English</option><option value="es">Español</option><option value="pt">Português</option></select></label>
              <label>Min words<input type="number" value={form.min_words} onChange={(e) => setForm({ ...form, min_words: Number(e.target.value) })} style={{ ...inputStyle, marginTop: 6 }} /></label>
              <label>Max words<input type="number" value={form.max_words} onChange={(e) => setForm({ ...form, max_words: Number(e.target.value) })} style={{ ...inputStyle, marginTop: 6 }} /></label>
              <label>Default ratio<select value={form.default_aspect_ratio} onChange={(e) => setForm({ ...form, default_aspect_ratio: e.target.value as ContentProfileInput["default_aspect_ratio"] })} style={{ ...inputStyle, marginTop: 6 }}><option value="16:9">16:9</option><option value="1:1">1:1</option><option value="4:5">4:5</option></select></label>
              <label>Default visual style<select value={form.default_visual_style} onChange={(e) => setForm({ ...form, default_visual_style: e.target.value })} style={{ ...inputStyle, marginTop: 6 }}><option value="">Default</option><option value="technical_editorial">Technical Editorial</option><option value="cinematic">Cinematic</option><option value="minimal">Minimal</option><option value="illustration">Illustration</option><option value="photorealistic">Photorealistic</option></select></label>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}><input type="checkbox" checked={form.visual_enabled} onChange={(e) => setForm({ ...form, visual_enabled: e.target.checked })} />Generate visual prompts for this profile</label>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 22 }}>
              <button disabled={saving || !form.name.trim() || form.min_words > form.max_words} onClick={save} style={{ ...inputStyle, width: "auto", cursor: "pointer", opacity: saving ? .6 : 1 }}>{saving ? "Saving…" : selected ? "Save profile" : "Create profile"}</button>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
