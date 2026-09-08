from __future__ import annotations

from domain.production.models import CarouselSpecV1, ContentSpecV1, InfographicSpecV1, SingleImageSpecV1
from domain.visual.models import DesignProfileV1, DiagramBlockV1, MetricBlockV1, TextBlockV1, VisualFormat, VisualSpecV1


class VisualSpecValidationError(ValueError):
    pass


def copy_reference_map(content: ContentSpecV1) -> dict[str, str]:
    refs: dict[str, str] = {
        "content_spec.hook": content.hook,
        "content_spec.body": content.body,
    }
    if content.title is not None:
        refs["content_spec.title"] = content.title
    if content.cta is not None:
        refs["content_spec.cta"] = content.cta
    if content.alt_text_draft is not None:
        refs["content_spec.alt_text_draft"] = content.alt_text_draft

    format_spec = content.format_spec
    if isinstance(format_spec, SingleImageSpecV1):
        refs["content_spec.format_spec.headline"] = format_spec.headline
        for index, item in enumerate(format_spec.supporting_copy):
            refs[f"content_spec.format_spec.supporting_copy[{index}]"] = item
        if format_spec.footer is not None:
            refs["content_spec.format_spec.footer"] = format_spec.footer
    elif isinstance(format_spec, CarouselSpecV1):
        for slide in format_spec.slides:
            prefix = f"content_spec.format_spec.slides[{slide.slide_id}]"
            refs[f"{prefix}.headline"] = slide.headline
            if slide.body is not None:
                refs[f"{prefix}.body"] = slide.body
            for index, bullet in enumerate(slide.bullets):
                refs[f"{prefix}.bullets[{index}]"] = bullet
    elif isinstance(format_spec, InfographicSpecV1):
        refs["content_spec.format_spec.title"] = format_spec.title
        for section in format_spec.sections:
            prefix = f"content_spec.format_spec.sections[{section.section_id}]"
            refs[f"{prefix}.label"] = section.label
            refs[f"{prefix}.value_or_copy"] = section.value_or_copy
            if section.relationship is not None:
                refs[f"{prefix}.relationship"] = section.relationship
    return refs


def resolve_copy_ref(content: ContentSpecV1, copy_ref: str) -> str:
    try:
        return copy_reference_map(content)[copy_ref]
    except KeyError as exc:
        raise VisualSpecValidationError(f"unknown copy_ref: {copy_ref}") from exc


def _critical_refs(spec: VisualSpecV1) -> set[str]:
    refs: set[str] = set()
    for page in spec.pages:
        for block in page.blocks:
            if isinstance(block, TextBlockV1) and block.editorial_critical and block.copy_ref:
                refs.add(block.copy_ref)
            elif isinstance(block, MetricBlockV1):
                refs.add(block.copy_ref)
                if block.label_ref:
                    refs.add(block.label_ref)
            elif isinstance(block, DiagramBlockV1):
                refs.update(block.label_refs)
    return refs


def _all_copy_refs(spec: VisualSpecV1) -> set[str]:
    refs: set[str] = set()
    for page in spec.pages:
        for block in page.blocks:
            if isinstance(block, TextBlockV1) and block.copy_ref:
                refs.add(block.copy_ref)
            elif isinstance(block, MetricBlockV1):
                refs.add(block.copy_ref)
                if block.label_ref:
                    refs.add(block.label_ref)
            elif isinstance(block, DiagramBlockV1):
                refs.update(block.label_refs)
    return refs


def _required_visual_refs(content: ContentSpecV1) -> set[str]:
    format_spec = content.format_spec
    if isinstance(format_spec, SingleImageSpecV1):
        refs = {"content_spec.format_spec.headline"}
        refs.update(f"content_spec.format_spec.supporting_copy[{index}]" for index in range(len(format_spec.supporting_copy)))
        if format_spec.footer is not None:
            refs.add("content_spec.format_spec.footer")
        return refs
    if isinstance(format_spec, CarouselSpecV1):
        refs: set[str] = set()
        for slide in format_spec.slides:
            prefix = f"content_spec.format_spec.slides[{slide.slide_id}]"
            refs.add(f"{prefix}.headline")
            if slide.body is not None:
                refs.add(f"{prefix}.body")
            refs.update(f"{prefix}.bullets[{index}]" for index in range(len(slide.bullets)))
        return refs
    if isinstance(format_spec, InfographicSpecV1):
        refs = {"content_spec.format_spec.title"}
        for section in format_spec.sections:
            prefix = f"content_spec.format_spec.sections[{section.section_id}]"
            refs.add(f"{prefix}.label")
            refs.add(f"{prefix}.value_or_copy")
            if section.relationship is not None:
                refs.add(f"{prefix}.relationship")
        return refs
    return set()


def validate_visual_spec(spec: VisualSpecV1, *, content: ContentSpecV1, design_profile: DesignProfileV1) -> None:
    if content.format == "text":
        raise VisualSpecValidationError("text-only ContentSpec does not require VisualSpec")
    if spec.content_spec_id != content.content_spec_id:
        raise VisualSpecValidationError("VisualSpec is bound to a different ContentSpec")
    if spec.format.value != content.format:
        raise VisualSpecValidationError("VisualSpec format does not match ContentSpec format")
    if spec.style.design_profile_ref != design_profile.design_profile_id:
        raise VisualSpecValidationError("VisualSpec references a different DesignProfile")
    if spec.style.design_profile_digest != design_profile.digest:
        raise VisualSpecValidationError("VisualSpec DesignProfile digest mismatch")
    if spec.style.density != design_profile.density:
        raise VisualSpecValidationError("VisualSpec density must come from DesignProfile")
    if spec.style.icon_language != design_profile.icon_language:
        raise VisualSpecValidationError("VisualSpec icon language must come from DesignProfile")
    if spec.style.image_treatment != design_profile.image_treatment:
        raise VisualSpecValidationError("VisualSpec image treatment must come from DesignProfile")

    inset = design_profile.safe_zone.inset_px
    safe_zone = spec.canvas.safe_zone
    if (safe_zone.top, safe_zone.right, safe_zone.bottom, safe_zone.left) != (inset, inset, inset, inset):
        raise VisualSpecValidationError("canvas safe zone must use the frozen DesignProfile policy")

    allowed_layouts = set(design_profile.layout_family_preferences)
    if any(page.layout_family not in allowed_layouts for page in spec.pages):
        raise VisualSpecValidationError("page layout family is outside DesignProfile preferences")

    copy_map = copy_reference_map(content)
    for ref in _all_copy_refs(spec):
        if ref not in copy_map:
            raise VisualSpecValidationError(f"unknown copy_ref: {ref}")

    missing = _required_visual_refs(content) - _critical_refs(spec)
    if missing:
        raise VisualSpecValidationError(f"critical visual copy coverage is incomplete: {sorted(missing)}")

    format_spec = content.format_spec
    if spec.format == VisualFormat.CAROUSEL:
        if not isinstance(format_spec, CarouselSpecV1):
            raise VisualSpecValidationError("carousel format contract mismatch")
        if len(spec.pages) != len(format_spec.slides):
            raise VisualSpecValidationError("carousel page count must equal accepted slide count")
        for page, slide in zip(spec.pages, format_spec.slides, strict=True):
            if page.role.value != slide.role:
                raise VisualSpecValidationError("carousel page order/role does not match ContentSpec")
    elif spec.format == VisualFormat.INFOGRAPHIC and not isinstance(format_spec, InfographicSpecV1):
        raise VisualSpecValidationError("infographic format contract mismatch")
    elif spec.format == VisualFormat.SINGLE_IMAGE and not isinstance(format_spec, SingleImageSpecV1):
        raise VisualSpecValidationError("single-image format contract mismatch")
