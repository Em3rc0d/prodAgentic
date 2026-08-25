import pytest

from core.content_identity import (
    CANONICALIZER_VERSION,
    build_content_identity,
    canonicalize_content,
    normalized_sha256,
)


def test_case_and_whitespace_variants_share_identity():
    a = "Our first AI agent architecture failed because every task was treated as an agent problem."
    b = "  our first AI AGENT architecture failed   because every task was treated as an agent problem.  "

    assert canonicalize_content(a) == canonicalize_content(b)
    assert normalized_sha256(a) == normalized_sha256(b)


def test_nfkc_normalizes_compatibility_characters():
    assert canonicalize_content("ＡＩ architecture") == canonicalize_content("AI architecture")


def test_punctuation_remains_part_of_v1_identity():
    assert normalized_sha256("Ship it.") != normalized_sha256("Ship it!")


def test_identity_records_canonicalizer_version():
    identity = build_content_identity("Technical content")
    assert identity.canonicalizer_version == CANONICALIZER_VERSION == "v1"
    assert len(identity.normalized_sha256) == 64


@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_blank_content_is_rejected(value):
    with pytest.raises(ValueError):
        normalized_sha256(value)


def test_non_string_content_is_rejected():
    with pytest.raises(TypeError):
        normalized_sha256(None)
