import hashlib
import unicodedata
from dataclasses import dataclass


CANONICALIZER_VERSION = "v1"


@dataclass(frozen=True)
class ContentIdentity:
    canonicalizer_version: str
    normalized_sha256: str


def canonicalize_content(text: str) -> str:
    """Return deterministic v1 content identity text.

    v1 intentionally normalizes Unicode compatibility forms, case and
    whitespace while preserving punctuation. Punctuation policy is part of
    the versioned contract and can evolve without changing historical hashes.
    """
    if not isinstance(text, str):
        raise TypeError("Content identity input must be a string")

    value = unicodedata.normalize("NFKC", text).casefold()
    value = " ".join(value.split()).strip()
    if not value:
        raise ValueError("Content identity input must not be blank")
    return value


def normalized_sha256(text: str) -> str:
    canonical = canonicalize_content(text)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_content_identity(text: str) -> ContentIdentity:
    return ContentIdentity(
        canonicalizer_version=CANONICALIZER_VERSION,
        normalized_sha256=normalized_sha256(text),
    )
