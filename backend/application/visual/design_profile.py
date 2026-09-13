from __future__ import annotations

import unicodedata

from domain.profiles.models import ProfileVersion
from domain.visual.models import (
    Density,
    DesignProfileV1,
    IconLanguage,
    ImageTreatment,
    LayoutFamily,
    PaletteMappingV1,
    RadiusScale,
    SafeZoneProfileV1,
    SpacingScale,
    TypographyRolesV1,
    canonical_visual_sha256,
)


def _normalize_trait(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


_SPARSE = {
    "minimal", "minimalist", "minimalista", "clean", "cleanly", "limpio",
    "premium", "elegant", "elegante", "sophisticated", "sofisticado",
}
_DENSE = {
    "technical", "tecnico", "data", "datos", "detailed", "detallado",
    "analytical", "analitico", "precise", "preciso",
}
_BOLD = {
    "bold", "energetic", "energetico", "aggressive", "agresivo",
    "impactful", "potente",
}
_DARK = {"dark", "oscuro", "dark-mode", "dark_mode"}
_SOFT = {"soft", "suave", "friendly", "amable", "approachable", "cercano", "warm", "calido"}


def derive_design_profile(profile: ProfileVersion) -> DesignProfileV1:
    """Derive a bounded cross-client visual archetype from ProfileVersion.

    Client specialization comes from explicit visual/voice traits. Unknown values
    never become token, CSS, URL or renderer authority. R3 varies density, layout,
    radius, icon language, image treatment, contrast and safe-zone policy while
    keeping the already-certified renderer token vocabulary closed.
    """

    traits = {_normalize_trait(item) for item in profile.visual_system.traits}
    sparse = bool(traits & _SPARSE)
    dense = bool(traits & _DENSE)
    bold = bool(traits & _BOLD)
    dark = bool(traits & _DARK)
    soft = bool(traits & _SOFT)

    if sparse and dense:
        density = Density.BALANCED
    elif sparse:
        density = Density.SPARSE
    elif dense:
        density = Density.DENSE
    else:
        density = Density.BALANCED

    accent = "accent.signal_strong" if bold else "accent.signal"
    if dark:
        palette = PaletteMappingV1(
            background="surface.ink",
            surface="surface.charcoal",
            text="text.on_dark",
            muted_text="text.muted_on_dark",
            accent=accent,
            border="border.dark_hairline",
        )
    else:
        palette = PaletteMappingV1(
            background="surface.canvas",
            surface="surface.paper",
            text="text.ink",
            muted_text="text.muted",
            accent=accent,
            border="border.hairline",
        )

    typography = TypographyRolesV1(
        display="type.editorial_display",
        heading="type.editorial_heading",
        body="type.editorial_body",
        mono="type.technical_mono",
    )

    if sparse:
        spacing = SpacingScale.ROOMY
        layouts = (
            LayoutFamily.HERO_STACK,
            LayoutFamily.SPLIT_FOCUS,
            LayoutFamily.EDITORIAL_POSTER,
        )
    elif dense:
        spacing = SpacingScale.COMPACT
        layouts = (
            LayoutFamily.EVIDENCE_GRID,
            LayoutFamily.METRIC_STACK,
            LayoutFamily.SPLIT_EVIDENCE,
        )
    else:
        spacing = SpacingScale.STANDARD
        layouts = (
            LayoutFamily.HERO_STACK,
            LayoutFamily.SPLIT_EVIDENCE,
            LayoutFamily.CARD_GRID,
        )

    if bold:
        icon_language = IconLanguage.EXPRESSIVE
        image_treatment = ImageTreatment.HIGH_CONTRAST
    elif dense:
        icon_language = IconLanguage.GEOMETRIC
        image_treatment = ImageTreatment.EDITORIAL_CROP
    else:
        icon_language = IconLanguage.OUTLINE
        image_treatment = ImageTreatment.MONOCHROME if sparse else ImageTreatment.EDITORIAL_CROP

    radius = RadiusScale.SOFT if soft else RadiusScale.SHARP if dense else RadiusScale.STANDARD
    inset = 84 if sparse else 64 if dense else 72

    semantic_payload = {
        "schema_version": 1,
        "mapping_version": "mk1-design-profile-v1",
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "source_profile_digest": profile.digest,
        "typography": typography.model_dump(mode="json"),
        "palette": palette.model_dump(mode="json"),
        "density": density.value,
        "spacing_scale": spacing.value,
        "radius_scale": radius.value,
        "icon_language": icon_language.value,
        "image_treatment": image_treatment.value,
        "layout_family_preferences": [item.value for item in layouts],
        "safe_zone": SafeZoneProfileV1(inset_px=inset).model_dump(mode="json"),
    }
    digest = canonical_visual_sha256(semantic_payload)
    return DesignProfileV1(
        design_profile_id=f"dp-{digest[:32]}",
        profile_id=profile.profile_id,
        profile_version=profile.version,
        source_profile_digest=profile.digest,
        typography=typography,
        palette=palette,
        density=density,
        spacing_scale=spacing,
        radius_scale=radius,
        icon_language=icon_language,
        image_treatment=image_treatment,
        layout_family_preferences=layouts,
        safe_zone=SafeZoneProfileV1(inset_px=inset),
        digest=digest,
    )
