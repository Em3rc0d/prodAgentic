from __future__ import annotations

import hashlib

from domain.quality.models import QACheckLayer, QACheckV1, QASeverity, RecoveryAction
from domain.rendering.models import AssetV1


def evaluate_owned_asset_bytes(asset: AssetV1, data: bytes) -> tuple[QACheckV1, ...]:
    actual_sha256 = hashlib.sha256(data).hexdigest()
    return (
        QACheckV1(
            code=f"asset.bytes.size.{asset.page_index}",
            layer=QACheckLayer.DETERMINISTIC,
            severity=QASeverity.BLOCKING,
            passed=len(data) == asset.byte_size,
            message="Owned asset byte length must exactly match immutable AssetV1 metadata.",
            target_ref=asset.asset_id,
            recovery_hint=RecoveryAction.VISUAL_REGEN,
        ),
        QACheckV1(
            code=f"asset.bytes.sha256.{asset.page_index}",
            layer=QACheckLayer.DETERMINISTIC,
            severity=QASeverity.BLOCKING,
            passed=actual_sha256 == asset.sha256,
            message="Owned asset bytes must exactly match immutable AssetV1 SHA-256 metadata.",
            target_ref=asset.asset_id,
            recovery_hint=RecoveryAction.VISUAL_REGEN,
        ),
    )
