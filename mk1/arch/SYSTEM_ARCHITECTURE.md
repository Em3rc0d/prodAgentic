# MK1 System Architecture

Status: **FROZEN**

## System view

```text
                     ┌──────────────────────────┐
                     │       Next.js UI         │
                     │ Home/Profile/Create/...  │
                     └─────────────┬────────────┘
                                   │ HTTPS/SSE
                     ┌─────────────▼────────────┐
                     │        FastAPI API        │
                     │ auth + application layer  │
                     └─────────────┬────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────▼────────┐   ┌──────────▼─────────┐   ┌─────────▼────────┐
│ Domain modules    │   │ Agent orchestration│   │ Product services  │
│ Profile/Batch/... │   │ planner + 4-agent  │   │ novelty/QA/render │
└─────────┬────────┘   └──────────┬─────────┘   └─────────┬────────┘
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   │ ports
     ┌─────────────────────────────┼──────────────────────────────┐
     │                             │                              │
┌────▼─────┐               ┌───────▼──────┐              ┌────────▼────────┐
│ MongoDB  │               │ Redis Streams│              │ AssetStore       │
│ authority│               │ transport    │              │ filesystem first │
└────┬─────┘               └───────┬──────┘              └────────┬────────┘
     │                             │                              │
     │                     ┌───────▼────────┐                     │
     │                     │ workers         │                     │
     │                     │ render/publish/ │                     │
     │                     │ analytics       │                     │
     │                     └───────┬────────┘                     │
     │                             │                              │
     └─────────────────────────────┼──────────────────────────────┘
                                   │ adapters
                      ┌────────────▼────────────┐
                      │ LLM/Image/LinkedIn/etc. │
                      └─────────────────────────┘
```

## Architectural layers

### Domain

Contains entities/value objects, state-transition rules, policies and repository interfaces. No HTTP, Redis, provider SDK or filesystem logic.

### Application

Use cases such as:

- CreateProfile / UpdateProfile;
- PlanBatch;
- ProduceContentItem;
- ReviewRevision;
- ApproveRevision;
- ScheduleApproval;
- DispatchDueSchedules;
- PublishApproval;
- ReconcilePublication;
- CollectMetrics;
- BuildPerformanceSummary.

Application services own orchestration order and transaction boundaries.

### Agent layer

Provides model-backed judgment through typed contracts. Agents do not mutate Mongo directly and do not call platform publishers.

### Infrastructure

Implements repositories, Redis transport, AssetStore, provider clients, renderer adapters and external platform adapters.

### Workers

Separately runnable processes using the same application/domain packages. V1 worker categories:

- render;
- publish;
- analytics.

Generation may initially run synchronously/streamed from the API for UX responsiveness while preserving persistent state. If generation moves to queue transport later, it must use the same contract model.

## Core data flow

```text
Intent
 -> ProfileVersion
 -> BatchPlan
 -> candidate pool
 -> novelty/diversity selection
 -> ContentItems
 -> ResearchPack
 -> ContentSpec
 -> EditorialReview
 -> ContentRevision
 -> VisualSpec
 -> Asset(s)
 -> QAReport
 -> human Review
 -> ApprovalBundle
 -> Schedule
 -> Outbox Job
 -> Redis
 -> Publication Claim
 -> PlatformAdapter
 -> Publication Receipt
 -> MetricSnapshots
 -> PerformanceSummary
 -> future BatchPlanner context
```

## Architecture boundaries deliberately retained from MK0

- FastAPI and Next.js foundations;
- MongoDB authority;
- versioned Profile snapshots;
- explicit immutable approval;
- exact asset digest verification;
- LinkedIn as first automatic adapter;
- no blind replay of uncertain external publication.

## New MK1 boundaries

- Tenant scope;
- Batch and ContentItem aggregates;
- GenerationRun separated from publish lifecycle;
- EditorialMemory and Novelty service;
- versioned structured contracts;
- VisualSpec IR;
- Asset/QA as first-class evidence;
- Redis Streams transport + Mongo outbox;
- capability contract for distribution;
- metric snapshots + summarized learning.

## Deployment shape V1

```text
frontend       Next.js
api            FastAPI
worker-render  same repository/package
worker-publish same repository/package
worker-metrics same repository/package
mongodb        durable
redis          disposable/recoverable transport
asset volume   durable
```

These may run on one machine/process group in early deployments. The logical boundaries remain the same.
