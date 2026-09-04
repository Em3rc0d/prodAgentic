import os
from dataclasses import dataclass
from enum import Enum


class FeatureFlag(str, Enum):
    MK1_ENABLED = "MK1_ENABLED"
    MK1_PROFILE_V2 = "MK1_PROFILE_V2"
    MK1_BATCH_PLANNING = "MK1_BATCH_PLANNING"
    MK1_STRUCTURED_AGENT_CELL = "MK1_STRUCTURED_AGENT_CELL"
    MK1_VISUALSPEC = "MK1_VISUALSPEC"
    MK1_RENDER_WORKER = "MK1_RENDER_WORKER"
    MK1_REDIS_TRANSPORT = "MK1_REDIS_TRANSPORT"
    MK1_PUBLISH_WORKER = "MK1_PUBLISH_WORKER"
    MK1_ANALYTICS_WORKER = "MK1_ANALYTICS_WORKER"
    MK1_PLANNER_LEARNING = "MK1_PLANNER_LEARNING"


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class FeatureFlagRegistry:
    values: dict[FeatureFlag, bool]

    @classmethod
    def from_env(cls) -> "FeatureFlagRegistry":
        values: dict[FeatureFlag, bool] = {}
        for flag in FeatureFlag:
            raw = os.environ.get(flag.value, "false").strip().lower()
            if raw not in _TRUE | _FALSE:
                raise ValueError(f"{flag.value} must be a boolean value")
            values[flag] = raw in _TRUE

        # A child authority cannot activate while the MK1 master gate is off.
        if not values[FeatureFlag.MK1_ENABLED]:
            values = {flag: False for flag in FeatureFlag}
        return cls(values=values)

    def enabled(self, flag: FeatureFlag) -> bool:
        return self.values.get(flag, False)

    def safe_snapshot(self) -> dict[str, bool]:
        return {flag.value: self.enabled(flag) for flag in FeatureFlag}
