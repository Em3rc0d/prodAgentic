"use client";

import { useEffect, useState } from "react";

import {
  acceptProfileV2,
  fetchProfilesV2,
  proposeProfileV2,
} from "@/lib/api";
import type {
  ProfileAccountType,
  ProfileChannel,
  ProfileGoal,
  ProfileInferenceProposalV1,
  ProfileSetupV2,
  ProfileV2,
} from "@/lib/api";
import styles from "./mk1-profile-setup.module.css";

const GOALS: Array<[ProfileGoal, string]> = [["grow", "Grow"], ["educate", "Educate"], ["build_authority", "Build authority"], ["sell", "Sell"], ["build_community", "Build community"], ["entertain", "Entertain"]];
const VOICES = ["direct", "professional", "close", "technical", "simple", "humorous"];
const CHANNELS: Array<[ProfileChannel, string]> = [["linkedin", "LinkedIn"], ["instagram", "Instagram"], ["tiktok", "TikTok"], ["manual_export", "Manual export"]];
const ACCOUNT_TYPES: Array<[ProfileAccountType, string]> = [["personal_brand", "Personal brand"], ["business", "Business"], ["education", "Education"], ["niche", "Niche"], ["other", "Other"]];

const INITIAL: ProfileSetupV2 = {
  name: "", account_type: "personal_brand", goals: ["educate"], audience: "",
  voice: ["direct"], batch_size: 4, channels: ["linkedin", "manual_export"], examples: [],
};

function toggle<T>(items: T[], item: T): T[] {
  return items.includes(item) ? items.filter((value) => value !== item) : [...items, item];
}

export function Mk1ProfileSetup() {
  const [step, setStep] = useState(0);
  const [setup, setSetup] = useState<ProfileSetupV2>(INITIAL);
  const [example, setExample] = useState("");
  const [proposal, setProposal] = useState<ProfileInferenceProposalV1 | null>(null);
  const [profiles, setProfiles] = useState<ProfileV2[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    fetchProfilesV2()
      .then((result) => setProfiles(result.profiles))
      .catch(() => setError("Profile library is temporarily unavailable"));
  }, []);

  async function review() {
    setBusy(true); setError(null);
    try {
      const nextSetup = example.trim()
        ? { ...setup, examples: [{ kind: "caption" as const, text: example.trim(), label: "Setup example" }] }
        : { ...setup, examples: [] };
      setSetup(nextSetup);
      setProposal(await proposeProfileV2(nextSetup));
      setStep(4);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not analyze this Profile"); }
    finally { setBusy(false); }
  }

  async function accept() {
    if (!proposal) return;
    setBusy(true); setError(null);
    try {
      const result = await acceptProfileV2(setup, proposal.proposal_digest);
      setProfiles((current) => [result.profile, ...current]);
      setSaved(`${result.profile.name} · Profile v${result.version.version}`);
      setStep(5);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save this Profile"); }
    finally { setBusy(false); }
  }

  const canContinue = [Boolean(setup.name.trim()), setup.goals.length > 0 && Boolean(setup.audience.trim()), setup.voice.length > 0 && setup.channels.length > 0, true][step] ?? true;

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div><span className={styles.kicker}>Profile intelligence</span><h1>Teach prodAgentic how to sound like you.</h1><p>Six clear choices. Advanced agent settings stay out of your way.</p></div>
        <span className={styles.counter}>{profiles.length} active</span>
      </header>

      <div className={styles.layout}>
        <aside className={styles.progress} aria-label="Profile setup progress">
          {["Identity", "Goal & audience", "Voice & channels", "Examples", "Confirm"].map((label, index) => <div key={label} className={index === step ? styles.current : index < step ? styles.done : ""}><span>{index < step ? "✓" : index + 1}</span>{label}</div>)}
        </aside>

        <section className={styles.card} aria-live="polite">
          {step === 0 && <><div className={styles.sectionTitle}><span>01</span><div><h2>Give this Profile an identity</h2><p>A useful internal name and the closest account type.</p></div></div><label>Name<input autoFocus value={setup.name} onChange={(event) => setSetup({ ...setup, name: event.target.value })} placeholder="e.g. Systems Field Notes" /></label><div className={styles.chips}>{ACCOUNT_TYPES.map(([value, label]) => <button key={value} aria-pressed={setup.account_type === value} className={setup.account_type === value ? styles.selected : ""} onClick={() => setSetup({ ...setup, account_type: value })}>{label}</button>)}</div></>}

          {step === 1 && <><div className={styles.sectionTitle}><span>02</span><div><h2>What should this Profile achieve?</h2><p>Pick one or more goals, then describe the people you want to help.</p></div></div><div className={styles.chips}>{GOALS.map(([value, label]) => <button key={value} aria-pressed={setup.goals.includes(value)} className={setup.goals.includes(value) ? styles.selected : ""} onClick={() => setSetup({ ...setup, goals: toggle(setup.goals, value) })}>{label}</button>)}</div><label>Audience<textarea value={setup.audience} onChange={(event) => setSetup({ ...setup, audience: event.target.value })} placeholder="drivers who want to care for used cars" /></label></>}

          {step === 2 && <><div className={styles.sectionTitle}><span>03</span><div><h2>Choose the voice and destinations</h2><p>Channels are editorial preferences. Connecting accounts happens separately.</p></div></div><span className={styles.label}>Voice</span><div className={styles.chips}>{VOICES.map((value) => <button key={value} aria-pressed={setup.voice.includes(value)} className={setup.voice.includes(value) ? styles.selected : ""} onClick={() => setSetup({ ...setup, voice: toggle(setup.voice, value) })}>{value}</button>)}</div><label>Optional nuance<input value={setup.voice_nuance ?? ""} onChange={(event) => setSetup({ ...setup, voice_nuance: event.target.value })} placeholder="Precise, but never cold" /></label><span className={styles.label}>Channels</span><div className={styles.chips}>{CHANNELS.map(([value, label]) => <button key={value} aria-pressed={setup.channels.includes(value)} className={setup.channels.includes(value) ? styles.selected : ""} onClick={() => setSetup({ ...setup, channels: toggle(setup.channels, value) })}>{label}</button>)}</div><span className={styles.label}>Content prepared at once</span><div className={styles.chips}>{[1, 4, 7].map((value) => <button key={value} aria-pressed={setup.batch_size === value} className={setup.batch_size === value ? styles.selected : ""} onClick={() => setSetup({ ...setup, batch_size: value })}>{value}</button>)}</div></>}

          {step === 3 && <><div className={styles.sectionTitle}><span>04</span><div><h2>Teach your style <em>optional</em></h2><p>Paste one caption or bio. We store evidence hashes in the accepted snapshot, not the raw example.</p></div></div><label>Example<textarea className={styles.example} value={example} onChange={(event) => setExample(event.target.value)} placeholder="Paste a caption, bio or short example…" /></label><button className={styles.skip} onClick={() => { setExample(""); review(); }}>Skip this step</button></>}

          {step === 4 && proposal && <><div className={styles.sectionTitle}><span>05</span><div><h2>This is what I understood.</h2><p>Nothing becomes authority until you accept it.</p></div></div><div className={styles.summary}><div><small>Identity</small><strong>{proposal.identity_summary}</strong></div><div><small>Audience</small><strong>{proposal.audience_segments.join(", ")}</strong></div><div><small>Voice</small><strong>{setup.voice.join(" · ")}</strong></div><div><small>Observed style</small><strong>{[proposal.caption_length_tendency, ...proposal.hook_tendencies].join(" · ")}</strong></div><div><small>Evidence</small><strong>{proposal.evidence.length} hashed example{proposal.evidence.length === 1 ? "" : "s"} · {proposal.confidence}</strong></div></div></>}

          {step === 5 && <div className={styles.complete}><span>✓</span><h2>Profile ready</h2><p>{saved}</p><small>The accepted settings are frozen. Future edits will create a new version.</small></div>}

          {error && <p role="alert" className={styles.error}>{error}</p>}
          {step < 5 && <footer className={styles.actions}>{step > 0 && <button className={styles.secondary} onClick={() => { setStep(step - 1); setProposal(null); }}>Back</button>}<span /><button className={styles.primary} disabled={busy || !canContinue} onClick={() => step < 3 ? setStep(step + 1) : step === 3 ? review() : accept()}>{busy ? "Working…" : step === 3 ? "Analyze" : step === 4 ? "Looks good" : "Continue"}</button></footer>}
        </section>
      </div>
    </main>
  );
}
