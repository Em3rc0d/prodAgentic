import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { Mk1ProfileSetup } from "@/components/mk1/Mk1ProfileSetup";
import * as api from "@/lib/api";

jest.mock("@/lib/api", () => ({
  fetchProfilesV2: jest.fn(),
  proposeProfileV2: jest.fn(),
  acceptProfileV2: jest.fn(),
}));

const mocked = api as jest.Mocked<typeof api>;

describe("MK1 low-friction Profile setup", () => {
  beforeEach(() => {
    mocked.fetchProfilesV2.mockResolvedValue({ profiles: [], count: 0 });
    mocked.proposeProfileV2.mockResolvedValue({
      schema_version: 1,
      setup_digest: "c".repeat(64),
      identity_summary: "Systems Field Notes: software engineers",
      audience_segments: ["software engineers"],
      topic_families: [],
      hook_tendencies: ["question"],
      caption_length_tendency: "short",
      cta_style: "question",
      evidence: [],
      confidence: "explicit_only",
      proposal_digest: "a".repeat(64),
    });
    mocked.acceptProfileV2.mockResolvedValue({
      profile: { profile_id: "p1", tenant_id: "t1", current_version: 1, name: "Systems Field Notes", status: "ACTIVE", created_at: "2026-09-04T00:00:00Z", updated_at: "2026-09-04T00:00:00Z" },
      version: { schema_version: 2, profile_id: "p1", tenant_id: "t1", version: 1, digest: "b".repeat(64), identity: { name: "Systems Field Notes", account_type: "education", summary: "Systems" }, audience: ["software engineers"], goals: ["educate"], copy_policy: { voice_traits: ["direct"] }, publishing_preferences: { channels: ["linkedin"], default_batch_size: 4 } },
    });
  });

  it("requires plain-language setup, previews inference, and accepts explicitly", async () => {
    render(<Mk1ProfileSetup />);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Systems Field Notes" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.change(screen.getByLabelText("Audience"), { target: { value: "software engineers" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Skip this step" }));

    await screen.findByRole("heading", { name: "This is what I understood." });
    expect(mocked.proposeProfileV2).toHaveBeenCalledTimes(1);
    expect(mocked.acceptProfileV2).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Looks good" }));
    await waitFor(() => expect(mocked.acceptProfileV2).toHaveBeenCalledWith(expect.any(Object), "a".repeat(64)));
    expect(await screen.findByRole("heading", { name: "Profile ready" })).toBeVisible();
    expect(screen.queryByText(/agent model/i)).not.toBeInTheDocument();
  });
});
