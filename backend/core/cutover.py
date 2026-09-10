from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse

from core.feature_flags import FeatureFlag
from db.mongo import database_ready

CUTOVER_ERROR_CODE = "MK0_WRITE_AUTHORITY_RETIRED"


@dataclass(frozen=True)
class LegacyWriteRule:
    methods: frozenset[str]
    exact_path: str | None = None
    path_prefix: str | None = None

    def matches(self, method: str, path: str) -> bool:
        normalized_method = method.upper()
        if normalized_method not in self.methods:
            return False
        if self.exact_path is not None:
            return path == self.exact_path
        if self.path_prefix is not None:
            return path.startswith(self.path_prefix)
        return False


# MK0 compatibility remains readable during the rollback window, but all paths
# below can create or mutate MK0 authority. pipeline/stream is intentionally
# included even though it is a GET because the legacy pipeline persists runs/posts.
LEGACY_WRITE_RULES: tuple[LegacyWriteRule, ...] = (
    LegacyWriteRule(frozenset({"POST"}), exact_path="/api/ideas"),
    LegacyWriteRule(frozenset({"GET"}), exact_path="/api/pipeline/stream"),
    LegacyWriteRule(frozenset({"POST"}), exact_path="/api/visual-renders"),
    LegacyWriteRule(frozenset({"PATCH", "POST", "DELETE"}), path_prefix="/api/content-runs/"),
    LegacyWriteRule(frozenset({"POST"}), exact_path="/api/content-profiles"),
    LegacyWriteRule(frozenset({"PATCH", "POST", "DELETE"}), path_prefix="/api/content-profiles/"),
    LegacyWriteRule(frozenset({"PATCH", "DELETE"}), path_prefix="/api/posts/"),
)


def is_legacy_write_authority(method: str, path: str) -> bool:
    return any(rule.matches(method, path) for rule in LEGACY_WRITE_RULES)


def legacy_replacement(path: str) -> str:
    if path.startswith("/api/content-profiles"):
        return "ProfileV2"
    if path.startswith("/api/posts"):
        return "ContentItem/PublicationV1"
    if path.startswith("/api/content-runs"):
        return "MK1 Revision/ApprovalV2/Schedule/PublicationV1"
    if path in {"/api/ideas", "/api/pipeline/stream"}:
        return "BatchPlanner + Structured Agent Cell"
    if path == "/api/visual-renders":
        return "VisualSpecV1 + Renderer"
    return "MK1"


async def production_cutover_boundary(request: Request, call_next):
    registry = getattr(request.app.state, "feature_flags", None)
    if (
        registry is not None
        and registry.enabled(FeatureFlag.MK1_PRODUCTION_CUTOVER)
        and is_legacy_write_authority(request.method, request.url.path)
    ):
        return JSONResponse(
            status_code=410,
            content={
                "detail": "MK0 write authority is retired while MK1 production cutover is active",
                "code": CUTOVER_ERROR_CODE,
                "replacement_authority": legacy_replacement(request.url.path),
            },
        )
    return await call_next(request)


def cutover_readiness(request: Request) -> tuple[dict, int]:
    registry = getattr(request.app.state, "feature_flags", None)
    container = getattr(request.app.state, "container", None)
    if registry is None:
        payload = {
            "status": "NOT_READY",
            "cutover_active": False,
            "reason": "Feature flags are not initialized",
        }
        return payload, 503

    cutover_active = registry.enabled(FeatureFlag.MK1_PRODUCTION_CUTOVER)
    flags = registry.safe_snapshot()
    db_ready = database_ready()

    scheduler = getattr(container, "scheduler_task", None) if container is not None else None
    publish_task = getattr(container, "s10_publish_task", None) if container is not None else None
    analytics_task = getattr(container, "s11_analytics_task", None) if container is not None else None

    scheduler_disabled = scheduler is None
    publish_worker_running = publish_task is not None and not publish_task.done()
    analytics_worker_running = analytics_task is not None and not analytics_task.done()

    ready = all(
        (
            cutover_active,
            db_ready,
            scheduler_disabled,
            publish_worker_running,
            analytics_worker_running,
        )
    )

    payload = {
        "status": "READY" if ready else "NOT_READY",
        "cutover_active": cutover_active,
        "feature_flags": flags,
        "database_ready": db_ready,
        "mk0_write_authority": "DISABLED" if cutover_active else "AVAILABLE_FOR_ROLLBACK",
        "mk0_scheduler": "DISABLED" if scheduler_disabled else "RUNNING",
        "mk1_publish_worker": "RUNNING" if publish_worker_running else "NOT_RUNNING",
        "mk1_analytics_worker": "RUNNING" if analytics_worker_running else "NOT_RUNNING",
        "provider_side_effect_authorization": "SEPARATE_OPERATOR_GATE",
    }
    return payload, 200 if ready else 503
