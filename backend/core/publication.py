import hashlib
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from core.content_memory import ContentMemoryService
from core.linkedin import (
    LinkedInPublishError,
    LinkedInPublishPhase,
    LinkedInPublisher,
    LinkedInPublisherConfig,
    PublicationRetrySafety,
)
from core.linkedin_oauth import LinkedInOAuthConfigurationError, LinkedInOAuthError, LinkedInOAuthService
from models.content_run import ContentRunStatus


logger = logging.getLogger(__name__)


class PublicationConflict(RuntimeError):
    pass


class PublicationUnavailable(RuntimeError):
    pass


class PublicationFailed(RuntimeError):
    pass


class PublicationReconciliationRequired(RuntimeError):
    pass


def _content_fingerprint(approval: dict) -> str:
    """Return the immutable text fingerprint used for publication deduplication."""
    fingerprint = approval.get("final_content_sha256")
    if isinstance(fingerprint, str) and fingerprint:
        return fingerprint

    final_content = approval.get("final_content")
    if not isinstance(final_content, str) or not final_content:
        raise PublicationConflict("Approved content is missing an immutable text fingerprint")
    return hashlib.sha256(final_content.encode("utf-8")).hexdigest()


def _publication_dedupe_key(author_urn: str, content_fingerprint: str) -> str:
    """Scope duplicate prevention to a LinkedIn identity and exact approved text."""
    raw = f"linkedin\n{author_urn}\n{content_fingerprint}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class PublicationCoordinator:
    """Single publication lifecycle used by manual and scheduled delivery."""

    def __init__(self, db, publisher_factory=None, config_factory=None, content_memory=None):
        self.db = db
        self.publisher_factory = publisher_factory or LinkedInPublisher
        self.config_factory = config_factory
        self.content_memory = content_memory or ContentMemoryService(db=db)

    async def resolve_config(self):
        """Resolve the canonical publication authority for every delivery path.

        Persisted LinkedIn OAuth is authoritative. Static token configuration is
        available only behind the explicit emergency/development fallback.
        """
        if self.config_factory is not None:
            return self.config_factory()

        try:
            return await LinkedInOAuthService(self.db).publisher_config()
        except (LinkedInOAuthConfigurationError, LinkedInOAuthError, LinkedInPublishError) as oauth_exc:
            static_fallback = os.environ.get("LINKEDIN_STATIC_FALLBACK_ENABLED", "false").strip().lower() in {
                "1", "true", "yes"
            }
            if not static_fallback:
                raise LinkedInPublishError(
                    str(oauth_exc),
                    retry_safety=PublicationRetrySafety.SAFE_TO_RETRY,
                    phase=LinkedInPublishPhase.CONFIG,
                ) from oauth_exc
            return LinkedInPublisherConfig.from_env()

    async def _index_published_memory(self, run_id: str, approval: dict, external_post_urn: str | None) -> None:
        """Best-effort projection only; publication authority has already succeeded."""
        try:
            await self.content_memory.index_published(run_id, approval, external_post_urn)
        except Exception as exc:
            logger.warning("Published content memory indexing degraded for run %s: %s", run_id, exc)

    async def _mark_safe_failure(
        self,
        *,
        collection,
        run_id: str,
        attempt_id: str,
        expected_status: ContentRunStatus,
        message: str,
        phase: str,
    ) -> None:
        failed_at = datetime.now(timezone.utc)
        fail_updates = {
            "status": ContentRunStatus.APPROVED.value,
            "publication.status": "FAILED",
            "publication.completed_at": failed_at,
            "publication.error_message": message,
            "publication.failure_retry_safety": PublicationRetrySafety.SAFE_TO_RETRY.value,
            "publication.failure_phase": phase,
            "updated_at": failed_at,
        }
        if expected_status == ContentRunStatus.SCHEDULED:
            fail_updates.update({
                "schedule.status": "FAILED",
                "schedule.completed_at": failed_at,
                "schedule.error_message": message,
            })
        await collection.update_one(
            {
                "run_id": run_id,
                "status": ContentRunStatus.PUBLISHING.value,
                "publication.attempt_id": attempt_id,
            },
            {"$set": fail_updates},
        )

    async def _mark_reconciliation_required(
        self,
        *,
        collection,
        run_id: str,
        attempt_id: str,
        expected_status: ContentRunStatus,
        message: str,
        phase: str,
    ) -> None:
        ambiguous_at = datetime.now(timezone.utc)
        updates = {
            # Root status deliberately remains PUBLISHING so ordinary retries
            # cannot replay an outcome that may already exist externally.
            "publication.status": "RECONCILIATION_REQUIRED",
            "publication.completed_at": ambiguous_at,
            "publication.error_message": message,
            "publication.failure_retry_safety": PublicationRetrySafety.RECONCILIATION_REQUIRED.value,
            "publication.failure_phase": phase,
            "updated_at": ambiguous_at,
        }
        if expected_status == ContentRunStatus.SCHEDULED:
            updates.update({
                "schedule.status": "RECONCILIATION_REQUIRED",
                "schedule.completed_at": ambiguous_at,
                "schedule.error_message": message,
            })
        await collection.update_one(
            {
                "run_id": run_id,
                "status": ContentRunStatus.PUBLISHING.value,
                "publication.attempt_id": attempt_id,
            },
            {"$set": updates},
        )

    async def publish_run(self, run_id: str, expected_status: ContentRunStatus = ContentRunStatus.APPROVED):
        collection = self.db["content_runs"]
        existing = await collection.find_one({"run_id": run_id})
        if existing is None:
            raise KeyError("Content run not found")

        approval = existing.get("approval")
        if not isinstance(approval, dict):
            raise PublicationConflict("Content run has no immutable approval snapshot")

        existing_publication = existing.get("publication") or {}
        if (
            existing.get("status") == ContentRunStatus.PUBLISHED.value
            and existing_publication.get("status") == "PUBLISHED"
            and existing_publication.get("bundle_sha256") == approval.get("bundle_sha256")
        ):
            # A successful receipt is terminal authority. Never contact LinkedIn
            # again; only heal the advisory memory projection if necessary.
            await self._index_published_memory(
                run_id,
                approval,
                existing_publication.get("external_post_urn"),
            )
            return await collection.find_one({"run_id": run_id})

        if existing.get("status") == ContentRunStatus.PUBLISHING.value:
            raise PublicationReconciliationRequired(
                "Publication is already in progress or requires reconciliation before retry"
            )

        if existing.get("status") != expected_status.value:
            raise PublicationConflict(
                f"Expected {expected_status.value} content; current status is {existing.get('status')}"
            )

        try:
            config = await self.resolve_config()
        except LinkedInPublishError as exc:
            # Authority resolution happens before entering PUBLISHING, so this is
            # safe to expose as unavailable without creating an ambiguous attempt.
            raise PublicationUnavailable(str(exc)) from exc

        content_fingerprint = _content_fingerprint(approval)
        dedupe_key = _publication_dedupe_key(config.author_urn, content_fingerprint)

        attempt_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        publication = {
            "provider": "linkedin",
            "status": "PUBLISHING",
            "attempt_id": attempt_id,
            "approval_id": approval["approval_id"],
            "bundle_sha256": approval["bundle_sha256"],
            "content_sha256": content_fingerprint,
            "dedupe_key": dedupe_key,
            "author_urn": config.author_urn,
            "started_at": started_at,
            "completed_at": None,
            "external_post_urn": None,
            "external_image_urn": None,
            "error_message": None,
            "failure_retry_safety": None,
            "failure_phase": None,
        }
        claim_updates = {
            "status": ContentRunStatus.PUBLISHING.value,
            "publication": publication,
            "updated_at": started_at,
        }
        if expected_status == ContentRunStatus.SCHEDULED:
            claim_updates.update({
                "schedule.status": "CLAIMED",
                "schedule.claimed_at": started_at,
            })

        try:
            claim = await collection.update_one(
                {
                    "run_id": run_id,
                    "status": expected_status.value,
                    "approval.approval_id": approval["approval_id"],
                    "approval.bundle_sha256": approval["bundle_sha256"],
                },
                {"$set": claim_updates},
            )
        except DuplicateKeyError as exc:
            raise PublicationConflict(
                "This exact approved text is already claimed or published for this LinkedIn identity"
            ) from exc

        if claim.matched_count == 0:
            raise PublicationConflict("Content run changed before publication could be claimed")

        publisher = self.publisher_factory(config)
        try:
            result = await publisher.publish(approval)
        except LinkedInPublishError as exc:
            if exc.retry_safety == PublicationRetrySafety.SAFE_TO_RETRY:
                await self._mark_safe_failure(
                    collection=collection,
                    run_id=run_id,
                    attempt_id=attempt_id,
                    expected_status=expected_status,
                    message=str(exc),
                    phase=exc.phase.value,
                )
                raise PublicationFailed(str(exc)) from exc

            await self._mark_reconciliation_required(
                collection=collection,
                run_id=run_id,
                attempt_id=attempt_id,
                expected_status=expected_status,
                message=str(exc),
                phase=exc.phase.value,
            )
            raise PublicationReconciliationRequired(str(exc)) from exc
        except Exception as exc:
            message = "Unexpected publisher outcome requires reconciliation"
            await self._mark_reconciliation_required(
                collection=collection,
                run_id=run_id,
                attempt_id=attempt_id,
                expected_status=expected_status,
                message=message,
                phase=LinkedInPublishPhase.UNKNOWN.value,
            )
            raise PublicationReconciliationRequired(message) from exc

        completed_at = datetime.now(timezone.utc)
        success_updates = {
            "status": ContentRunStatus.PUBLISHED.value,
            "publication.status": "PUBLISHED",
            "publication.completed_at": completed_at,
            "publication.external_post_urn": result.post_urn,
            "publication.external_image_urn": result.image_urn,
            "publication.failure_retry_safety": None,
            "publication.failure_phase": None,
            "updated_at": completed_at,
        }
        if expected_status == ContentRunStatus.SCHEDULED:
            success_updates.update({
                "schedule.status": "COMPLETED",
                "schedule.completed_at": completed_at,
                "schedule.error_message": None,
            })

        final_update = await collection.update_one(
            {"run_id": run_id, "status": ContentRunStatus.PUBLISHING.value, "publication.attempt_id": attempt_id},
            {"$set": success_updates},
        )
        if final_update.matched_count == 0:
            raise PublicationReconciliationRequired(
                "LinkedIn accepted the post but local publication evidence could not be finalized; manual reconciliation required"
            )

        await self._index_published_memory(run_id, approval, result.post_urn)
        return await collection.find_one({"run_id": run_id})
