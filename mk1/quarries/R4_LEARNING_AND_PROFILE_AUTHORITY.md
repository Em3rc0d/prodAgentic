# Quarry — R4 Learning Loop and Profile Authority

Status: **CLOSED DESIGN FINDING / PROMOTE TO R4**

## Question

How can prodAgentic learn continuously without turning analytics/model output into silent authority over the user’s identity?

## Finding

The correct boundary is a typed `LearningProposal` between observational data and Profile authority.

```text
AnalyticsSnapshot / EditorialMemory
              ↓
       LearningProposal
              ↓
   policy classification
      ↙             ↘
low-risk weight   semantic change
      ↓             ↓
auditable update  HumanProfileDecision
                    ↓
                ProfileVersion+1
```

## LearningProposal minimum contract

```text
proposal_id
profile_id
source_snapshot_ids[]
source_memory_ids[]
proposal_type
current_value
proposed_value
rationale
confidence
risk_class
created_at
state = PROPOSED | ACCEPTED | REJECTED | EXPIRED
```

No proposal is allowed to contain secrets or infer sensitive personal attributes from engagement data.

## Risk classes

### OPERATIONAL

Examples: topic-weight adjustment, format-frequency preference, caption-length tendency, scheduling preference when supported by channel data.

May be auto-applied only under an explicit policy that records old value, new value, reason and rollback path. The change must not alter the user’s declared identity or protected semantic constraints.

### SEMANTIC

Examples: audience definition, brand positioning, primary goals, forbidden topics, voice identity, account type.

Requires explicit human decision. Acceptance creates a new immutable ProfileVersion. Rejection remains evidence and must not be reproposed continuously without new supporting evidence.

## Anti-feedback-loop rules

- One successful post cannot rewrite strategy.
- Performance is contextual; the system must distinguish weak evidence from repeated patterns.
- Novelty remains a constraint even if one topic performs well.
- Engagement cannot justify clickbait or unsupported claims.
- The system should preserve exploration budget so optimization does not collapse the account into one format/topic.
- Historical versions and the evidence behind each accepted learning change remain queryable.

## Profile legacy repair

Malformed historical profile derivations are not “learning”. They are data-quality debt.

Repair path:

```text
Profile v1
  ↓
LegacyProfileDiagnostic
  ↓
NormalizationProposal
  ↓
Human confirm material semantic changes
  ↓
Profile v2
```

The original Profile v1 remains immutable so older content lineage continues to verify.

## Promotion

This finding closes the R4 design gap represented by `learning-proposal` and `human-profile-decision` in the certification graph. Implementation and tests remain open; design closure does not equal runtime certification.
