from core.linkedin_text import normalize_linkedin_plain_text


def test_normalizer_removes_escaped_and_markdown_presentation_markers():
    source = (
        r"Tratar el \*grounding\* y **trust boundary** con `GroundingPolicy`."
        "\n\n"
        "## Una idea"
    )

    assert normalize_linkedin_plain_text(source) == (
        "Tratar el grounding y trust boundary con GroundingPolicy.\n\nUna idea"
    )


def test_normalizer_preserves_unmatched_technical_asterisks():
    source = "SELECT * FROM runs\nchar *ptr = value;"

    assert normalize_linkedin_plain_text(source) == source


def test_normalizer_collapses_repeated_blank_lines_but_preserves_paragraphs():
    source = "Primero.\n\n\n\nSegundo.\n\n\nTercero."

    assert normalize_linkedin_plain_text(source) == "Primero.\n\nSegundo.\n\nTercero."


def test_normalizer_removes_code_fence_marker_without_rewriting_content():
    source = "```\nGroundingPolicy -> PASS\n```"

    assert normalize_linkedin_plain_text(source) == "GroundingPolicy -> PASS"
