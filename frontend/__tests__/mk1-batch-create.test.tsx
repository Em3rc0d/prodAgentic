import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { Mk1BatchCreate } from "@/components/mk1/Mk1BatchCreate";
import * as api from "@/lib/api";
import * as batches from "@/lib/mk1-batches";

jest.mock("@/lib/api", () => ({ fetchProfilesV2: jest.fn() }));
jest.mock("@/lib/mk1-batches", () => ({ createBatchV1: jest.fn() }));

const mockedApi = api as jest.Mocked<typeof api>;
const mockedBatches = batches as jest.Mocked<typeof batches>;

const profile = {
  profile_id: "profile-1",
  tenant_id: "tenant-a",
  current_version: 3,
  name: "Logan",
  status: "ACTIVE" as const,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
};

function response(selectedSize = 4) {
  const contentItems = Array.from({ length: selectedSize }, (_, index) => ({
    content_id: `content-${index}`,
    batch_id: "batch-1",
    profile_id: "profile-1",
    profile_version: 3,
    canonical_topic: `topic.${index}`,
    subtopics: [],
    angle: `fresh angle ${index}`,
    role: ["safety", "maintenance", "symptom", "mechanical_explainer"][index % 4],
    target_effect: "useful outcome",
    format: ["single_image", "carousel", "text", "infographic"][index % 4] as batches.PlannedFormat,
    hook_pattern: ["warning", "checklist", "question", "diagram_flow"][index % 4],
    editorial_state: "PLANNED" as const,
  }));
  const evaluations = contentItems.map((item, index) => ({
    candidate: {
      candidate_id: `candidate-${index}`,
      role: item.role,
      topic: item.canonical_topic,
      angle: item.angle,
      hook_pattern: item.hook_pattern,
      tentative_format: item.format,
    },
    novelty: {
      novelty_result_id: `novelty-${index}`,
      verdict: index === 0 ? "PASS_WITH_WARNING" as const : "PASS" as const,
      canonical_topic: item.canonical_topic,
      reasons: [],
      cooldown_band: "ELIGIBLE" as const,
    },
    selected: true,
    selection_reason: "selected",
  }));
  return {
    batch: {
      batch_id: "batch-1",
      tenant_id: "tenant-a",
      profile_id: "profile-1",
      profile_version: 3,
      profile_snapshot_digest: "a".repeat(64),
      target_window: { start_at: "2026-09-06T05:00:00Z", end_at: "2026-09-07T05:00:00Z", timezone: "America/Lima" },
      requested_size: 4,
      selected_size: selectedSize,
      state: selectedSize === 4 ? "PLANNED" as const : "PARTIAL" as const,
      shortfall_reason: selectedSize === 4 ? null : `Selected ${selectedSize} of 4; hard novelty/diversity gates were not relaxed to fill the batch.`,
      summary_counts: { candidates_generated: 12, candidates_blocked: 2, candidates_rewrite: 1, candidates_warning: 1, selected: selectedSize },
    },
    content_items: contentItems,
    plans: contentItems.map((item, index) => ({
      artifact_id: `plan-${index}`,
      digest: "b".repeat(64),
      content_id: item.content_id,
      plan: { candidate_id: `candidate-${index}`, novelty_result_ref: `novelty-${index}`, profile_id: "profile-1", profile_version: 3 },
    })),
    planning_trace: { trace_id: "trace-batch-1", digest: "c".repeat(64), evaluations },
    memory_count: 9,
  };
}

describe("MK1 S2 Create", () => {
  beforeEach(() => {
    mockedApi.fetchProfilesV2.mockResolvedValue({ profiles: [profile], count: 1 });
    mockedBatches.createBatchV1.mockResolvedValue(response());
  });

  it("starts with outcome-level controls and plans four pieces by default", async () => {
    render(<Mk1BatchCreate />);
    expect(await screen.findByRole("heading", { name: "Create for Logan" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Tomorrow" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "4" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByLabelText("Goal")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Generate next batch" }));
    await waitFor(() => expect(mockedBatches.createBatchV1).toHaveBeenCalledTimes(1));
    expect(mockedBatches.createBatchV1.mock.calls[0][0]).toBe("profile-1");
    expect(mockedBatches.createBatchV1.mock.calls[0][1].requested_size).toBe(4);
    expect(mockedBatches.createBatchV1.mock.calls[0][1].target_window.timezone).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "4 of 4 ideas committed" })).toBeVisible();
    expect(screen.getByText("Fresh · review note")).toBeVisible();
    expect(screen.getByText(/12 candidates evaluated/i)).toBeVisible();
  });

  it("tells the truth when novelty returns fewer items", async () => {
    mockedBatches.createBatchV1.mockResolvedValueOnce(response(2));
    render(<Mk1BatchCreate />);
    await screen.findByRole("heading", { name: "Create for Logan" });
    fireEvent.click(screen.getByRole("button", { name: "Generate next batch" }));
    expect(await screen.findByRole("heading", { name: "2 of 4 ideas committed" })).toBeVisible();
    expect(screen.getByText("We returned fewer ideas instead of repeating recent content.")).toBeVisible();
    expect(screen.getByText(/were not relaxed to fill the batch/i)).toBeVisible();
  });

  it("keeps optional constraints out of the primary path", async () => {
    render(<Mk1BatchCreate />);
    await screen.findByRole("heading", { name: "Create for Logan" });
    fireEvent.click(screen.getByRole("button", { name: "Add optional constraints" }));
    fireEvent.change(screen.getByLabelText("Goal"), { target: { value: "teach safe maintenance" } });
    fireEvent.change(screen.getByLabelText("Avoid for this batch"), { target: { value: "llantas, aceite" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate next batch" }));
    await waitFor(() => expect(mockedBatches.createBatchV1).toHaveBeenCalled());
    const request = mockedBatches.createBatchV1.mock.calls.at(-1)?.[1];
    expect(request?.constraints?.campaign_goal).toBe("teach safe maintenance");
    expect(request?.constraints?.avoid_topics).toEqual(["llantas", "aceite"]);
  });
});
