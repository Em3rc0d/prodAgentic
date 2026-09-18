import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { Mk1BatchCreate } from "@/components/mk1/Mk1BatchCreate";
import * as api from "@/lib/api";
import * as batches from "@/lib/mk1-batches";
import * as r2 from "@/lib/r2";
import * as production from "@/lib/r2-production";

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: mockPush }) }));
jest.mock("@/lib/api", () => ({ fetchProfilesV2: jest.fn() }));
jest.mock("@/lib/mk1-batches", () => ({ createBatchV1: jest.fn(), fetchBatchV1: jest.fn() }));
jest.mock("@/lib/r2", () => ({ fetchRuntimeReadiness: jest.fn() }));
jest.mock("@/lib/r2-production", () => ({
  produceContentToReview: jest.fn(),
  resumeContentToReview: jest.fn(),
  fetchContentRecovery: jest.fn(),
  recoverContent: jest.fn(),
}));

const mockedApi = api as jest.Mocked<typeof api>;
const mockedBatches = batches as jest.Mocked<typeof batches>;
const mockedR2 = r2 as jest.Mocked<typeof r2>;
const mockedProduction = production as jest.Mocked<typeof production>;

const profile = {
  profile_id: "profile-1",
  tenant_id: "tenant-a",
  current_version: 3,
  name: "Logan",
  status: "ACTIVE" as const,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
};

function planned(contentId = "content-0"): batches.BatchPlanningResponseV1 {
  return {
    batch: {
      batch_id: "batch-1",
      tenant_id: "tenant-a",
      profile_id: "profile-1",
      profile_version: 3,
      profile_snapshot_digest: "a".repeat(64),
      target_window: {
        start_at: "2026-09-17T05:00:00Z",
        end_at: "2026-09-18T05:00:00Z",
        timezone: "America/Lima",
      },
      requested_size: 1,
      selected_size: 1,
      state: "PLANNED",
      shortfall_reason: null,
      summary_counts: {
        candidates_generated: 4,
        candidates_blocked: 0,
        candidates_rewrite: 0,
        candidates_warning: 0,
        selected: 1,
      },
    },
    content_items: [{
      content_id: contentId,
      batch_id: "batch-1",
      profile_id: "profile-1",
      profile_version: 3,
      canonical_topic: "systems.recovery",
      subtopics: [],
      angle: "recover from an authoritative failure",
      role: "education",
      target_effect: "show recovery semantics",
      format: "single_image",
      hook_pattern: "question",
      editorial_state: "PLANNED",
    }],
    plans: [{
      artifact_id: "plan-0",
      digest: "b".repeat(64),
      content_id: contentId,
      plan: {
        candidate_id: "candidate-0",
        novelty_result_ref: "novelty-0",
        profile_id: "profile-1",
        profile_version: 3,
      },
    }],
    planning_trace: {
      trace_id: "trace-1",
      digest: "c".repeat(64),
      evaluations: [{
        candidate: {
          candidate_id: "candidate-0",
          role: "education",
          topic: "systems.recovery",
          angle: "recover from an authoritative failure",
          hook_pattern: "question",
          tentative_format: "single_image",
        },
        novelty: {
          novelty_result_id: "novelty-0",
          verdict: "PASS",
          canonical_topic: "systems.recovery",
          reasons: [],
          cooldown_band: "ELIGIBLE",
        },
        selected: true,
        selection_reason: "selected",
      }],
    },
    memory_count: 2,
  };
}

function decision(action: production.RecoveryAction, contentId = "content-0"): production.RecoveryDecision {
  return {
    content_id: contentId,
    run_id: `run-${contentId}`,
    action,
    code: action === "REPLAN_CONTENT" ? "RESEARCH_NO_GO" : action === "RESUME_PIPELINE" ? "PERSISTED_REVISION" : "MODEL_TIMEOUT",
    stage: action === "RESUME_PIPELINE" ? "rendering" : "research",
    retryable: action !== "REPLAN_CONTENT",
    safe_message: action === "REPLAN_CONTENT" ? "Replace the rejected idea." : action === "RESUME_PIPELINE" ? "Continue from the saved draft." : "Retry the failed production run.",
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  mockedApi.fetchProfilesV2.mockResolvedValue({ profiles: [profile], count: 1 });
  mockedBatches.createBatchV1.mockResolvedValue(planned());
  mockedR2.fetchRuntimeReadiness.mockResolvedValue({ state: "READY", label: "Runtime ready", detail: "READY" });
  mockedProduction.produceContentToReview.mockRejectedValue(new Error("fixture production failure"));
});

it("keeps RETRY_PRODUCTION as an explicit per-piece action", async () => {
  const recovery = decision("RETRY_PRODUCTION");
  mockedProduction.fetchContentRecovery.mockResolvedValue(recovery);
  mockedProduction.recoverContent.mockResolvedValue({
    content_id: "content-0",
    revision_id: "revision-recovered",
    format: "single_image",
    reviewable: true,
  });

  render(<Mk1BatchCreate />);
  await screen.findByRole("heading", { name: "Create for Logan" });
  fireEvent.click(screen.getByRole("button", { name: "Generate next batch" }));

  const button = await screen.findByRole("button", { name: "Retry production" });
  expect(mockedProduction.recoverContent).not.toHaveBeenCalled();
  fireEvent.click(button);

  await waitFor(() => expect(mockedProduction.recoverContent).toHaveBeenCalled());
  expect(mockedProduction.recoverContent.mock.calls[0][0]).toBe("content-0");
  expect(mockedProduction.recoverContent.mock.calls[0][1]).toEqual(recovery);
  expect(await screen.findByText("Ready for review")).toBeVisible();
});

it("automatically resumes a retryable persisted pipeline failure", async () => {
  const recovery = decision("RESUME_PIPELINE");
  mockedProduction.fetchContentRecovery.mockResolvedValue(recovery);
  mockedProduction.recoverContent.mockResolvedValue({
    content_id: "content-0",
    revision_id: "revision-recovered",
    format: "single_image",
    reviewable: true,
  });

  render(<Mk1BatchCreate />);
  await screen.findByRole("heading", { name: "Create for Logan" });
  fireEvent.click(screen.getByRole("button", { name: "Generate next batch" }));

  await waitFor(() => expect(mockedProduction.recoverContent).toHaveBeenCalledTimes(1));
  expect(mockedProduction.recoverContent.mock.calls[0][0]).toBe("content-0");
  expect(mockedProduction.recoverContent.mock.calls[0][1]).toEqual(recovery);
  expect(await screen.findByText("Ready for review")).toBeVisible();
});

it("replans through the governed replacement identity before marking the replacement reviewable", async () => {
  const recovery = decision("REPLAN_CONTENT");
  const replacement = planned("content-replacement");
  mockedProduction.fetchContentRecovery.mockResolvedValue(recovery);
  mockedBatches.fetchBatchV1.mockResolvedValue(replacement);
  mockedProduction.recoverContent.mockImplementation(async (_contentId, _decision, _onStage, onReplacement) => {
    if (onReplacement) await onReplacement("content-replacement");
    return {
      content_id: "content-replacement",
      revision_id: "revision-replacement",
      format: "single_image",
      reviewable: true,
    };
  });

  render(<Mk1BatchCreate />);
  await screen.findByRole("heading", { name: "Create for Logan" });
  fireEvent.click(screen.getByRole("button", { name: "Generate next batch" }));

  await waitFor(() => expect(mockedProduction.recoverContent).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(mockedBatches.fetchBatchV1).toHaveBeenCalledWith("batch-1"));
  expect(mockedProduction.recoverContent.mock.calls[0][0]).toBe("content-0");
  expect(mockedProduction.recoverContent.mock.calls[0][1]).toEqual(recovery);
  expect(await screen.findByText("Ready for review")).toBeVisible();
});
