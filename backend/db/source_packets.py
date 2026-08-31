from models.grounding import SourcePacket


class SourcePacketRepository:
    """Persistence boundary for immutable pre-generation evidence packets."""

    def __init__(self, db):
        self.db = db
        self.collection = db["source_packets"]

    async def create(self, packet: SourcePacket) -> SourcePacket:
        doc = packet.model_dump(mode="python")
        await self.collection.insert_one(doc)
        return packet

    async def get(self, workspace_id: str, packet_id: str) -> SourcePacket | None:
        doc = await self.collection.find_one(
            {"workspace_id": workspace_id, "packet_id": packet_id},
            {"_id": 0},
        )
        if doc is None:
            return None
        return SourcePacket.model_validate(doc)

    async def list_recent(self, workspace_id: str, limit: int = 25) -> list[SourcePacket]:
        cursor = (
            self.collection.find(
                {"workspace_id": workspace_id},
                {"_id": 0},
            )
            .sort("created_at", -1)
            .limit(limit)
        )
        packets: list[SourcePacket] = []
        async for doc in cursor:
            packets.append(SourcePacket.model_validate(doc))
        return packets
