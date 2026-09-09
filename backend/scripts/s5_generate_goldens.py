from __future__ import annotations

import asyncio
import json
import os
import struct
from datetime import datetime, timezone
from pathlib import Path

from application.rendering.copy_resolver import build_renderer_request
from application.visual.design_profile import derive_design_profile
from application.visual.planner import build_visual_spec
from domain.profiles.models import (
    AccountType,
    AgentPolicy,
    Channel,
    ClaimPolicy,
    CopyPolicy,
    EditorialStrategy,
    Goal,
    MigrationProvenance,
    NoveltyPolicy,
    ProfileIdentity,
    ProfileVersion,
    PublishingPreferences,
    VisualSystem,
    canonical_digest as profile_digest,
)
from domain.production.models import (
    CarouselSlideV1,
    CarouselSpecV1,
    ContentSpecV1,
    InfographicSectionV1,
    InfographicSpecV1,
    SingleImageSpecV1,
)
from infrastructure.assets.filesystem import FilesystemAssetStore
from infrastructure.rendering.chromium import ChromiumRendererAdapter


NOW = datetime(2026, 9, 8, 20, 45, tzinfo=timezone.utc)


def make_profile(profile_id: str, name: str, traits: tuple[str, ...]) -> ProfileVersion:
    provisional = ProfileVersion(
        profile_id=profile_id,
        tenant_id="tenant-s5-goldens",
        version=1,
        identity=ProfileIdentity(
            name=name,
            account_type=AccountType.NICHE,
            summary=f"S5 golden render fixture for {name}",
        ),
        goals=(Goal.EDUCATE,),
        audience=("people who value concise, trustworthy visual explanations",),
        editorial_strategy=EditorialStrategy(topic_families=("education", "systems")),
        novelty_policy=NoveltyPolicy(),
        copy_policy=CopyPolicy(voice_traits=("clear", "confident"), target_language="es"),
        claim_policy=ClaimPolicy(),
        visual_system=VisualSystem(traits=traits),
        publishing_preferences=PublishingPreferences(
            channels=(Channel.LINKEDIN, Channel.INSTAGRAM),
            default_batch_size=4,
        ),
        agent_policy=AgentPolicy(),
        provenance=MigrationProvenance(source="USER_ACCEPTED"),
        accepted_at=NOW,
        created_at=NOW,
        digest="0" * 64,
    )
    return provisional.model_copy(update={"digest": profile_digest(provisional)})


def content_seller() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-seller-s5-golden",
        plan_id="plan-content-seller-s5-golden",
        language="es",
        title="Content Seller",
        hook="El diseño no debe inventar el mensaje.",
        body="Una pieza clara conserva el copy aceptado y usa la composición para hacerlo memorable.",
        cta="Guárdalo como regla de producción.",
        alt_text_draft="Póster editorial que explica que el renderer compone copy previamente aceptado.",
        format="single_image",
        format_spec=SingleImageSpecV1(
            headline="Diseña el mensaje. No lo vuelvas a inventar.",
            supporting_copy=(
                "El copy crítico viene del ContentSpec.",
                "El renderer convierte intención en composición verificable.",
            ),
            footer="prodAgentic · deterministic visual production",
        ),
    )


def logan() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="logan-s5-golden",
        plan_id="plan-logan-s5-golden",
        language="es",
        title="Logan · educación automotriz",
        hook="Antes de cambiar piezas, confirma la señal.",
        body="Un diagnóstico responsable separa observación de conclusión.",
        cta="Observa, registra y confirma.",
        alt_text_draft="Carrusel de dos páginas sobre diagnóstico automotriz responsable.",
        format="carousel",
        format_spec=CarouselSpecV1(
            slides=(
                CarouselSlideV1(
                    slide_id="observe",
                    role="hook",
                    headline="Primero observa el síntoma",
                    body="Ruido, vibración o testigo son señales. Todavía no son un diagnóstico.",
                ),
                CarouselSlideV1(
                    slide_id="confirm",
                    role="takeaway",
                    headline="Luego confirma antes de reemplazar",
                    bullets=(
                        "Registra cuándo aparece la señal.",
                        "Contrasta evidencia antes de cambiar piezas.",
                    ),
                ),
            )
        ),
    )


def tech() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="tech-s5-golden",
        plan_id="plan-tech-s5-golden",
        language="en",
        title="Tech / LinkedIn",
        hook="A release is not a green icon. It is a chain of evidence.",
        body="Exact source identity, reproducible checks, and owned artifacts keep delivery inspectable.",
        alt_text_draft="Technical infographic showing the path from source identity to verified release evidence.",
        format="infographic",
        format_spec=InfographicSpecV1(
            title="From source to verified release",
            sections=(
                InfographicSectionV1(
                    section_id="source",
                    label="Commit",
                    value_or_copy="Immutable source identity",
                    relationship="feeds exact-SHA CI",
                ),
                InfographicSectionV1(
                    section_id="ci",
                    label="CI",
                    value_or_copy="Reproducible verification",
                    relationship="produces evidence",
                ),
                InfographicSectionV1(
                    section_id="artifact",
                    label="Artifact",
                    value_or_copy="Owned bytes + digest",
                    relationship="becomes inspectable release input",
                ),
            )
        ),
    )


def png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError("renderer returned invalid PNG bytes")
    return struct.unpack(">II", data[16:24])


async def render_golden(
    *,
    line: str,
    profile: ProfileVersion,
    content: ContentSpecV1,
    renderer: ChromiumRendererAdapter,
    store: FilesystemAssetStore,
    evidence_root: Path,
) -> dict:
    design = derive_design_profile(profile)
    revision_id = f"revision-{line}"
    visual = build_visual_spec(
        visual_spec_id=f"visual-{line}",
        revision_id=revision_id,
        content=content,
        design_profile=design,
    )
    request = build_renderer_request(
        revision_id=revision_id,
        visual_spec=visual,
        content=content,
        design_profile=design,
        renderer_name=renderer.name,
        renderer_version=renderer.version,
    )
    pages = await renderer.render(request)
    if len(pages) != len(visual.pages):
        raise RuntimeError(f"{line}: renderer page count mismatch")

    line_dir = evidence_root / line
    line_dir.mkdir(parents=True, exist_ok=True)
    manifest_pages = []
    for expected, page in zip(visual.pages, pages, strict=True):
        width, height = png_dimensions(page.data)
        if (width, height) != (visual.canvas.width, visual.canvas.height):
            raise RuntimeError(f"{line}: actual PNG dimensions mismatch")
        stored = await store.put(
            page.data,
            tenant_id=profile.tenant_id,
            revision_id=revision_id,
            render_id=request.render_id,
            page_index=page.page_index,
            content_type=page.content_type,
        )
        if not await store.verify(stored.storage_key, stored.sha256):
            raise RuntimeError(f"{line}: AssetStore read-back verification failed")
        owned_bytes = await store.get(stored.storage_key)
        output_path = line_dir / f"page-{page.page_index:02d}.png"
        output_path.write_bytes(owned_bytes)
        manifest_pages.append(
            {
                "page_id": expected.page_id,
                "page_index": expected.page_index,
                "width": width,
                "height": height,
                "byte_size": stored.byte_size,
                "sha256": stored.sha256,
                "storage_key": stored.storage_key,
                "evidence_file": str(output_path.relative_to(evidence_root)),
            }
        )

    return {
        "line": line,
        "profile_id": profile.profile_id,
        "profile_digest": profile.digest,
        "content_spec_id": content.content_spec_id,
        "visual_spec_id": visual.visual_spec_id,
        "design_profile_id": design.design_profile_id,
        "format": content.format,
        "render_id": request.render_id,
        "render_input_digest": request.render_input_digest,
        "renderer_name": renderer.name,
        "renderer_version": renderer.version,
        "page_count": len(manifest_pages),
        "pages": manifest_pages,
    }


async def main() -> None:
    evidence_root = Path(os.environ.get("S5_GOLDEN_OUTPUT_ROOT", "../s5-cert-evidence/goldens")).resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    asset_root = evidence_root / "owned-assetstore"
    renderer = ChromiumRendererAdapter()
    store = FilesystemAssetStore(asset_root)

    cases = (
        (
            "content-seller",
            make_profile("profile-content-seller", "Content Seller", ("clean", "friendly", "bold")),
            content_seller(),
        ),
        (
            "logan",
            make_profile("profile-logan", "Logan Automotive", ("technical", "bold")),
            logan(),
        ),
        (
            "tech",
            make_profile("profile-tech", "Tech LinkedIn", ("clean", "technical")),
            tech(),
        ),
    )

    manifests = []
    for line, profile, content in cases:
        manifests.append(
            await render_golden(
                line=line,
                profile=profile,
                content=content,
                renderer=renderer,
                store=store,
                evidence_root=evidence_root,
            )
        )

    manifest = {
        "schema_version": 1,
        "generated_at": NOW.isoformat(),
        "canvas": {"width": 1080, "height": 1350},
        "goldens": manifests,
    }
    (evidence_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"goldens": [(item["line"], item["page_count"]) for item in manifests]}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
