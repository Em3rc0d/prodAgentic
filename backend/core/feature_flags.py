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
    MK1_REVIEW_APPROVAL = "MK1_REVIEW_APPROVAL"
    MK1_MANUAL_EXPORT = "MK1_MANUAL_EXPORT"
    MK1_REDIS_TRANSPORT = "MK1_REDIS_TRANSPORT"
    MK1_PUBLISH_WORKER = "MK1_PUBLISH_WORKER"
    MK1_ANALYTICS_WORKER = "MK1_ANALYTICS_WORKER"
    MK1_PLANNER_LEARNING = "MK1_PLANNER_LEARNING"
    MK1_PRODUCTION_CUTOVER = "MK1_PRODUCTION_CUTOVER"


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}

_CUTOVER_REQUIRED_FLAGS = (
    FeatureFlag.MK1_ENABLED,
    FeatureFlag.MK1_PROFILE_V2,
    FeatureFlag.MK1_BATCH_PLANNING,
    FeatureFlag.MK1_STRUCTURED_AGENT_CELL,
    FeatureFlag.MK1_VISUALSPEC,
    FeatureFlag.MK1_RENDER_WORKER,
    FeatureFlag.MK1_REVIEW_APPROVAL,
    FeatureFlag.MK1_MANUAL_EXPORT,
    FeatureFlag.MK1_REDIS_TRANSPORT,
    FeatureFlag.MK1_PUBLISH_WORKER,
    FeatureFlag.MK1_ANALYTICS_WORKER,
    FeatureFlag.MK1_PLANNER_LEARNING,
)


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

        # Production cutover is an authority claim, not a convenience flag.
        # It fails closed if any certified V1 child authority is omitted.
        if values[FeatureFlag.MK1_PRODUCTION_CUTOVER]:
            missing = [flag.value for flag in _CUTOVER_REQUIRED_FLAGS if not values[flag]]
            if missing:
                raise ValueError(
                    "MK1_PRODUCTION_CUTOVER requires all certified MK1 V1 authorities; "
                    f"missing: {', '.join(missing)}"
                )

        # A child authority cannot activate while the MK1 master gate is off.
        if not values[FeatureFlag.MK1_ENABLED]:
            values = {flag: False for flag in FeatureFlag}
        return cls(values=values)

    def enabled(self, flag: FeatureFlag) -> bool:
        return self.values.get(flag, False)

    def safe_snapshot(self) -> dict[str, bool]:
        return {flag.value: self.enabled(flag) for flag in FeatureFlag}
