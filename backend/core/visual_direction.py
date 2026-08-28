from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


class VisualFormat(str, Enum):
    TECHNICAL_DIAGRAM = "TECHNICAL_DIAGRAM"
    ARCHITECTURE_SCHEMATIC = "ARCHITECTURE_SCHEMATIC"
    PROCESS_FLOW = "PROCESS_FLOW"
    COMPARISON = "COMPARISON"
    ARTIFACT_BOARD = "ARTIFACT_BOARD"
    EDITORIAL_POSTER = "EDITORIAL_POSTER"
    ILLUSTRATION = "ILLUSTRATION"


@dataclass(frozen=True)
class VisualDirection:
    visual_format: VisualFormat
    composition: str
    treatment: str
    recommended_aspect_ratio: str = "4:5"
    recommended_style: str = "technical_editorial"


class VisualDirectionPolicy:
    """Deterministically choose a visual communication format before prompting AI.

    The policy is intentionally boring code: an image model may execute the
    direction, but it cannot decide that every software topic deserves the same
    neon/cyberpunk metaphor.
    """

    VERSION = "visual-direction-policy-v1"

    _COMPARISON = re.compile(
        r"\b(vs\.?|versus|compar(?:a|ar|ación)|antes\s+y\s+después|before\s+and\s+after|before/after|trade-?off)\b",
        re.IGNORECASE,
    )
    _ARTIFACT = re.compile(
        r"\b(ci/?cd|github|pull request|\bpr\b|commit|pytest|test(?:s|ing)?|terminal|traceback|log(?:s)?|release|deploy|build|docker|workflow|pipeline failure)\b",
        re.IGNORECASE,
    )
    _ARCHITECTURE = re.compile(
        r"\b(arquitectura|architecture|system design|microserv(?:ice|icio)|kafka|rag|distributed|distribuid|event(?:o|s)?|broker|queue|sourcepacket|grounding|oauth|api gateway|database|base de datos|mongo(?:db)?|spring boot)\b",
        re.IGNORECASE,
    )
    _PROCESS = re.compile(
        r"\b(pipeline|flujo|workflow|proceso|process|paso(?:s)?|stage(?:s)?|fase(?:s)?|validaci[oó]n|verification|verificaci[oó]n|retry|reintento|fallback|extract|match|approve|publish)\b",
        re.IGNORECASE,
    )
    _STRONG_POSITION = re.compile(
        r"\b(no deber[ií]a|nunca|jam[aá]s|the hard part|el verdadero riesgo|la regla|no es|debe|should never|must not)\b",
        re.IGNORECASE,
    )

    _DIRECTIONS = {
        VisualFormat.TECHNICAL_DIAGRAM: VisualDirection(
            visual_format=VisualFormat.TECHNICAL_DIAGRAM,
            composition=(
                "One central technical concept expressed with 3–5 simple geometric components, "
                "clear directional relationships, strong negative space and one obvious focal point."
            ),
            treatment=(
                "Premium technical editorial graphic: crisp vector-like geometry, restrained contrast, "
                "subtle depth only where useful, no decorative sci-fi effects."
            ),
        ),
        VisualFormat.ARCHITECTURE_SCHEMATIC: VisualDirection(
            visual_format=VisualFormat.ARCHITECTURE_SCHEMATIC,
            composition=(
                "A clean system schematic with a small number of boxes/nodes, arrows and one highlighted "
                "trust boundary or decision point; hierarchy must be understandable at feed size."
            ),
            treatment=(
                "Modern architecture-document aesthetic, precise spacing, thin technical lines, restrained "
                "accent color, matte background, no photorealistic server rooms."
            ),
        ),
        VisualFormat.PROCESS_FLOW: VisualDirection(
            visual_format=VisualFormat.PROCESS_FLOW,
            composition=(
                "A vertical or stepped flow of 4–6 stages with one explicit gate/failure branch and a clear "
                "before→after reading direction."
            ),
            treatment=(
                "Editorial process diagram with disciplined grid, simple icons/shapes and strong hierarchy; "
                "communicate sequence rather than spectacle."
            ),
        ),
        VisualFormat.COMPARISON: VisualDirection(
            visual_format=VisualFormat.COMPARISON,
            composition=(
                "A deliberate split composition contrasting two approaches, with matched geometry and one "
                "clear difference emphasized between left/right or before/after."
            ),
            treatment=(
                "Minimal editorial comparison graphic; asymmetric accent only on the important difference, "
                "no dramatic scenery."
            ),
        ),
        VisualFormat.ARTIFACT_BOARD: VisualDirection(
            visual_format=VisualFormat.ARTIFACT_BOARD,
            composition=(
                "A curated engineering artifact board: abstract terminal/CI/PR/log fragments, one highlighted "
                "failure or decision, arranged like a premium technical case-study plate."
            ),
            treatment=(
                "Build-in-public editorial aesthetic, realistic software artifacts without fake brand marks or "
                "invented metrics; clean grid, subtle paper/screen texture, restrained accent."
            ),
        ),
        VisualFormat.EDITORIAL_POSTER: VisualDirection(
            visual_format=VisualFormat.EDITORIAL_POSTER,
            composition=(
                "One bold conceptual statement represented by a single simple visual tension, plenty of empty "
                "space and a strong poster-like focal point; avoid dense decoration."
            ),
            treatment=(
                "Swiss/editorial poster sensibility, geometric precision, high contrast, restrained palette, "
                "confident rather than sensational."
            ),
        ),
        VisualFormat.ILLUSTRATION: VisualDirection(
            visual_format=VisualFormat.ILLUSTRATION,
            composition=(
                "One concrete metaphor grounded in the post, limited to a few objects and a readable silhouette; "
                "the metaphor must communicate the idea without generic AI symbolism."
            ),
            treatment=(
                "Sophisticated editorial illustration, tactile and restrained; no cyberpunk, no holograms, no "
                "glowing brains, no generic futuristic workspace."
            ),
        ),
    }

    @classmethod
    def select(cls, content: str, *, style: str = "educational") -> VisualDirection:
        text = content or ""

        if cls._COMPARISON.search(text):
            return cls._DIRECTIONS[VisualFormat.COMPARISON]
        if cls._ARTIFACT.search(text):
            return cls._DIRECTIONS[VisualFormat.ARTIFACT_BOARD]
        if cls._ARCHITECTURE.search(text) and cls._PROCESS.search(text):
            return cls._DIRECTIONS[VisualFormat.ARCHITECTURE_SCHEMATIC]
        if cls._PROCESS.search(text):
            return cls._DIRECTIONS[VisualFormat.PROCESS_FLOW]
        if cls._ARCHITECTURE.search(text):
            return cls._DIRECTIONS[VisualFormat.ARCHITECTURE_SCHEMATIC]
        if style == "controversial" or cls._STRONG_POSITION.search(text):
            return cls._DIRECTIONS[VisualFormat.EDITORIAL_POSTER]
        if style == "storytelling":
            return cls._DIRECTIONS[VisualFormat.ILLUSTRATION]
        return cls._DIRECTIONS[VisualFormat.TECHNICAL_DIAGRAM]

    @classmethod
    def render_for_agent(cls, direction: VisualDirection) -> str:
        return "\n".join(
            [
                "<VISUAL_DIRECTION_DATA>",
                f"policy_version={cls.VERSION}",
                f"format={direction.visual_format.value}",
                f"recommended_aspect_ratio={direction.recommended_aspect_ratio}",
                f"recommended_style={direction.recommended_style}",
                f"composition={direction.composition}",
                f"treatment={direction.treatment}",
                "AUTHORITY RULE: This block controls visual communication format. Do not replace it with a different art genre.",
                "</VISUAL_DIRECTION_DATA>",
            ]
        )
