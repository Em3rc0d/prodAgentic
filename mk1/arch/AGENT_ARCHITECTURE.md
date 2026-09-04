# MK1 Agent Architecture

Status: **FROZEN**

## Principle

An agent exists only where semantic judgment, language reasoning or creative synthesis is required.

Deterministic work — state transitions, hashes, scheduling, dedupe, storage, schema checks, queueing, byte verification — stays normal software.

## Two orchestration levels

### Level A — Batch planning

`BatchPlanner` is an application service. It may use a model-backed `CandidatePlannerAgent` to propose candidates, but selection remains governed by deterministic/policy services such as Novelty and Diversity.

```text
Profile + Memory + Strategy
    -> CandidatePlannerAgent
    -> IdeaCandidateV1[]
    -> Novelty/Diversity/Policy
    -> ContentPlanV1[]
```

### Level B — Four-agent production cell

Each selected ContentItem runs the canonical production cell:

```text
ResearchAgent
    -> ResearchPackV1
WriterAgent
    -> ContentSpecV1
EditorAgent
    -> EditorialReviewV1 + accepted/revised ContentSpecV1
VisualAgent
    -> VisualSpecV1
```

This is the four-agent cell referred to in MK1 product design. Planner is upstream orchestration/planning, not a fifth content-production stage.

# ResearchAgent

## Job

Establish what may safely be said for this ContentPlan.

## Inputs

- ContentPlanV1;
- ProfileVersion claim policy;
- research depth policy;
- allowed evidence tools/sources;
- target language/context.

## Output

`ResearchPackV1` with:

- verdict `GO | GO_WITH_CAUTION | NO_GO`;
- key points;
- claims with confidence/evidence refs;
- uncertainties;
- safety notes;
- forbidden/unsupported claims;
- recommended framing.

## Research depth

Policy-resolved examples:

```text
meme/personal low-risk      -> minimal
technical explainer         -> standard
safety/health/regulated-ish -> high or block depending domain policy
```

The user normally does not choose this manually.

# WriterAgent

## Job

Transform approved research and plan intent into platform-neutral structured copy.

## Inputs

- ContentPlanV1;
- ResearchPackV1;
- ProfileVersion copy policy;
- target format/platform hints.

## Output

`ContentSpecV1`, including structured title/hook/body/CTA and format-specific slide/scene/frame semantics.

## Authority limit

Writer cannot create unsupported factual claims. New claims not represented in ResearchPack must be removed or sent back for research.

# EditorAgent

## Job

Act as editorial gate for clarity, brand fit, momentum, platform fit and supported claims.

## Checks

- brand match;
- clarity;
- hook strength;
- factual consistency;
- repetition inside copy;
- CTA quality;
- platform limits;
- claim qualification.

## Verdict

```text
APPROVE_TEXT
REVISE
REJECT
```

The editor may revise style/structure but may not introduce new unsupported claims.

# VisualAgent

## Job

Act as visual director, not image-prompt-only generator.

## Inputs

- accepted ContentSpecV1;
- Profile visual system;
- target format/platform canvas constraints;
- available asset capabilities.

## Output

`VisualSpecV1` describing pages, layout families, copy references, asset requirements, render strategy and visual semantics.

Critical editorial text references the accepted ContentSpec rather than being freely regenerated.

# Model routing

Each agent declares a model profile rather than a hard-coded provider/model:

```text
PLANNING_ECONOMY
RESEARCH_STANDARD
RESEARCH_HIGH
WRITING_STANDARD
EDITOR_QUALITY
VISUAL_PLANNING
VISION_QA
```

`ModelRouter` resolves provider/model based on:

- capability;
- tenant/plan budget;
- availability;
- configured preference;
- task risk/depth.

Provider/model identity is recorded in AgentRun evidence.

# AgentRun evidence

Every call/attempt records safe metadata:

```text
agent_run_id
agent
contract_version
prompt_version
provider
model
attempt
latency
tokens/cost when available
input_digest
output_digest
result status
safe failure code
```

Raw secrets and unnecessary user content are not copied into operational logs.

# Retry taxonomy

### Transient technical

Timeout, 429, provider 5xx: bounded retry/fallback according to router policy.

### Contract failure

Invalid structured output: schema repair/regen within bounded contract-repair budget.

### Domain failure

`ResearchPack.NO_GO`: do not retry the same claim blindly. Replan/replace candidate.

### Editorial failure

Editor reject: return to Writer with explicit issues or replace plan after bounded revision budget.

### Visual failure

Renderer/visual QA may recompose/rerender without rerunning research/copy unless dependency rules require it.

# Default retry budgets

Initial V1 policy:

- model transient attempts per route: 2 retries after first attempt;
- structured-output repair: max 2 repairs;
- writer/editor revision loop: max 2 cycles;
- visual layout recovery: max 2 rerenders/recompositions;
- candidate refill after planning gates: max 2 bounded refill rounds.

Budgets are configurable policy and always recorded. Exhaustion escalates to a safe failure/attention state rather than infinite loops.
