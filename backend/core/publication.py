import os
from datetime import datetime, timezone
from uuid import uuid4

from core.linkedin import LinkedInPublishError, LinkedInPublisher, LinkedInPublisherConfig
from core.linkedin_oauth import LinkedInOAuthConfigurationError, LinkedInOAuthError, LinkedInOAuthService
from models.content_run import ContentRunStatus


class PublicationConflict(RuntimeError):
    pass


class PublicationUnavailable(RuntimeError):
    pass


class PublicationFailed(RuntimeError):
    pass


class PublicationReconciliationRequired(RuntimeError):
    pass


class PublicationCoordinator:
    """Single publication lifecycle used by manual and scheduled delivery."""

    def __init__(self, db, publisher_factory=None, config_factory=None):
        self.db = db
        self.publisher_factory = publisher_factory or LinkedInPublisher
        self.config_factory = config_factory

    async def resolve_config(self):
        """Resolve the canonical publication authority for manual and scheduled delivery.

        Persisted LinkedIn OAuth is authoritative in normal production. Static token
        configuration is available only when the explicit emergency/dev fallback is
        enabled, so every publication entry point observes the same policy.
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
                raise LinkedInPublishError(str(oauth_exc)) from oauth_exc
            return LinkedInPublisherConfig.from_env()

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
            return existing

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
            raise PublicationUnavailable(str(exc)) from exc

        attempt_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        publication = {
            "provider": "linkedin",
            "status": "PUBLISHING",
            "attempt_id": attempt_id,
            "approval_id": approval["approval_id"],
            "bundle_sha256": approval["bundle_sha256"],
            "author_urn": config.author_urn,
            "started_at": started_at,
            "completed_at": None,
            "external_post_urn": None,
            "external_image_urn": None,
            "error_message": None,
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

        claim = await collection.update_one(
            {
                "run_id": run_id,
                "status": expected_status.value,
                "approval.approval_id": approval["approval_id"],
                "approval.bundle_sha256": approval["bundle_sha256"],
            },
            {"$set": claim_updates},
        )
        if claim.matched_count == 0:
            raise PublicationConflict("Content run changed before publication could be claimed")

        publisher = self.publisher_factory(config)
        try:
            result = await publisher.publish(approval)
        except LinkedInPublishError as exc:
            failed_at = datetime.now(timezone.utc)
            fail_updates = {
                "status": ContentRunStatus.APPROVED.value,
                "publication.status": "FAILED",
                "publication.completed_at": failed_at,
                "publication.error_message": str(exc),
                "updated_at": failed_at,
            }
            if expected_status == ContentRunStatus.SCHEDULED:
                fail_updates.update({
                    "schedule.status": "FAILED",
                    "schedule.completed_at": failed_at,
                    "schedule.error_message": str(exc),
                })
            await collection.update_one(
                {"run_id": run_id, "status": ContentRunStatus.PUBLISHING.value, "publication.attempt_id": attempt_id},
                {"$set": fail_updates},
            )
            raise PublicationFailed(str(exc)) from exc
        except Exception as exc:
            failed_at = datetime.now(timezone.utc)
            fail_updates = {
                "status": ContentRunStatus.APPROVED.value,
                "publication.status": "FAILED",
                "publication.completed_at": failed_at,
                "publication.error_message": "Unexpected publisher failure",
                "updated_at": failed_at,
            }
            if expected_status == ContentRunStatus.SCHEDULED:
                fail_updates.update({
                    "schedule.status": "FAILED",
                    "schedule.completed_at": failed_at,
                    "schedule.error_message": "Unexpected publisher failure",
                })
            await collection.update_one(
                {"run_id": run_id, "status": ContentRunStatus.PUBLISHING.value, "publication.attempt_id": attempt_id},
                {"$set": fail_updates},
            )
            raise PublicationFailed("Unexpected publisher failure") from exc

        completed_at = datetime.now(timezone.utc)
        success_updates = {
            "status": ContentRunStatus.PUBLISHED.value,
            "publication.status": "PUBLISHED",
            "publication.completed_at": completed_at,
            "publication.external_post_urn": result.post_urn,
            "publication.external_image_urn": result.image_urn,
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

        return await collection.find_one({"run_id": run_id})
