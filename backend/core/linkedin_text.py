from __future__ import annotations

import re


_HEADING_PREFIX = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+")
_BOLD_ASTERISK = re.compile(r"\*\*([^*\n]+?)\*\*")
_BOLD_UNDERSCORE = re.compile(r"__([^_\n]+?)__")
_ITALIC_ASTERISK = re.compile(r"(?<!\w)\*([^*\n]+?)\*(?!\w)")
_ITALIC_UNDERSCORE = re.compile(r"(?<!\w)_([^_\n]+?)_(?!\w)")
_INLINE_CODE = re.compile(r"`([^`\n]+?)`")


def normalize_linkedin_plain_text(text: str) -> str:
    """Normalize generated post prose to LinkedIn-safe plain text.

    LinkedIn post bodies do not interpret Markdown. This function deliberately
    removes common presentation-only Markdown while preserving the underlying
    words, URLs, technical identifiers, paragraph boundaries and unmatched
    punctuation such as SQL '*' or pointer syntax.
    """
    if not text:
        return text

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    # Models sometimes escape Markdown emphasis even though the destination is
    # plain text (for example: \*grounding\*). Unescape before removing paired
    # presentation markers.
    normalized = normalized.replace(r"\*", "*").replace(r"\_", "_").replace(r"\`", "`")

    normalized = _HEADING_PREFIX.sub("", normalized)
    normalized = normalized.replace("```", "")
    normalized = _BOLD_ASTERISK.sub(r"\1", normalized)
    normalized = _BOLD_UNDERSCORE.sub(r"\1", normalized)
    normalized = _ITALIC_ASTERISK.sub(r"\1", normalized)
    normalized = _ITALIC_UNDERSCORE.sub(r"\1", normalized)
    normalized = _INLINE_CODE.sub(r"\1", normalized)

    lines = [line.rstrip() for line in normalized.split("\n")]
    compacted: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if compacted and not blank:
                compacted.append("")
            blank = True
            continue
        compacted.append(line)
        blank = False

    return "\n".join(compacted).strip()
