from __future__ import annotations

from domain.publishing.models import PublicationState
from application.publishing.service import PublishingAuthorityError, utc_now


class ReconciliationService:
    def __init__(self, *, publications, schedules, connections, adapter):
        self.publications = publications
        self.schedules = schedules
        self.connections = connections
        self.adapter = adapter

    async def reconcile(self, publication_id: str):
        publication = await self.publications.get(publication_id)
        if publication is None:
            raise PublishingAuthorityError("Publication not found")
        if publication.state is PublicationState.PUBLISHED:
            return publication
        if publication.state is not PublicationState.RECONCILIATION_REQUIRED:
            raise PublishingAuthorityError("Only RECONCILIATION_REQUIRED publication can be reconciled")

        connection = await self.connections.get_linkedin()
        if connection is None:
            return publication
        receipt = await self.adapter.reconcile(publication, connection)
        if receipt is None:
            return publication
        resolved = await self.publications.resolve_reconciliation_published(
            publication.publication_id,
            receipt=receipt,
            now=utc_now(),
        )
        if resolved is None:
            raise PublishingAuthorityError("Publication changed while reconciliation was being finalized")
        if resolved.schedule_id:
            await self.schedules.mark_completed(resolved.schedule_id, utc_now())
        return resolved
