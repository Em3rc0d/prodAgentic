# Brainstorming — Content Intelligence

Status: ACCEPTED FOR DESIGN

## Core question

What can make prodAgentic exceptional without turning it into an expensive always-on personal AI system?

## Starting observations

The current product already solves several difficult workflow problems:

- generation is persisted as a `ContentRun`,
- profiles are snapshotted,
- review is explicit,
- approval freezes exact content and optional visual bytes,
- scheduling and publication share one coordinator,
- publication is evidence-backed and idempotent at the approved-bundle boundary.

Therefore the next differentiator should deepen content intelligence around this lifecycle rather than create a parallel agent platform.

## Candidate ideas considered

### A. Persistent per-user Brain

Idea: maintain a continuously learning semantic/personality model for every user.

Potential value:
- high personalization,
- long-term learning,
- potentially strong demo effect.

Risks:
- infrastructure and inference grows with users,
- hidden profile drift,
- difficult debugging,
- ambiguous consent/authority,
- expensive background work,
- easy to overfit isolated interactions,
- hard to guarantee tenant isolation.

Decision: REJECT for current program.

### B. Continuous behavioral learning

Idea: silently learn voice/preferences from every edit, approval, rejection and publication.

Potential value:
- low onboarding friction.

Risks:
- one client-specific edit can poison a personal profile,
- context-specific behavior becomes incorrectly global,
- user cannot easily explain why output changed,
- requires more state and inference logic than proven value justifies.

Decision: REJECT as an automatic system. Future explicit one-time analysis may be considered.

### C. Semantic Content Memory

Idea: persist a compact searchable representation of content history and compare new ideas/posts on demand.

Value:
- prevents repeated content,
- directly strengthens Content Library,
- differentiates from stateless generation,
- small persisted footprint,
- compute only at ingest/check time,
- workspace-scoped by design.

Decision: ACCEPT — CI-01.

### D. Source-grounded generation

Idea: attach explicit source records/snapshots to a ContentRun and allow strict generation modes using those sources.

Value:
- trust and traceability,
- practical for technical/expert content,
- source use can be inspected later,
- does not require global knowledge ingestion.

Risks:
- large sources can increase token cost,
- stale source snapshots,
- unsafe assumption that source presence equals factual correctness.

Decision: ACCEPT with bounded source selection — CI-02.

### E. Claim-level Evidence Graph

Idea: map every claim in final content to one or more source spans.

Value:
- very strong trust feature.

Risks:
- materially more inference and UX complexity,
- claim extraction and entailment become a new subsystem,
- not needed to prove initial market value of grounding.

Decision: DEFER. Run-level source traceability first.

### F. Visual Intelligence

Idea: classify the communicative job of the visual before generating a prompt.

Value:
- fixes the current bias toward cinematic metaphors,
- better technical communication,
- one small inference/decision step per visual request,
- reuses existing renderer and artifact evidence.

Decision: ACCEPT — CI-03.

### G. Analytics feedback loop

Idea: learn future strategy from impressions, comments, likes and other platform analytics.

Value:
- potentially strong long-term moat.

Risks:
- requires reliable analytics access,
- significant data volume before conclusions are meaningful,
- polling/background complexity,
- easy to optimize vanity metrics.

Decision: DEFER until real user data proves need.

### H. Opportunity mining from repositories/docs

Idea: user explicitly selects a source and asks prodAgentic to discover publishable ideas not already covered.

Value:
- uses Content Memory and grounding together,
- useful for technical users.

Risk:
- source connector breadth can expand scope rapidly.

Decision: ACCEPT LATER, on-demand only.

## Product thesis

The exceptional version of prodAgentic is not the AI that knows everything about the user.

It is the system that reliably knows:

- what content was generated,
- what was approved,
- what was published,
- what idea is being repeated,
- what sources were deliberately used,
- what visual form best communicates the content,
- and what external publication evidence exists.

## Decision filters for every future feature

A proposal must answer YES to at least one:

1. Does it increase publication reliability?
2. Does it increase durable content memory?
3. Does it increase grounding/traceability?
4. Does it materially improve communication quality?
5. Does it reduce repeated user work?

And it must answer NO to both unless explicitly justified:

1. Does it require meaningful compute while the user is idle?
2. Does it create a separate per-user runtime/service?

## Initial program scope

IN:
- CI-01 Semantic Content Memory,
- CI-02 Source-Grounded ContentRuns,
- CI-03 Visual Intelligence,
- Golden Dataset for all three,
- scale/cost constraints,
- non-regression gates around existing publication lifecycle.

OUT:
- analytics learning,
- autonomous content strategy,
- personal Brain,
- social network expansion,
- broad connector marketplace,
- claim-level evidence graph,
- realtime monitoring.