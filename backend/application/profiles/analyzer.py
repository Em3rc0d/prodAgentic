import hashlib
import re
import unicodedata
from collections import Counter

from domain.profiles.models import (
    InferenceEvidence,
    ProfileInferenceProposal,
    ProfileSetup,
    canonical_digest,
)


_STOPWORDS = {
    # Spanish
    "a", "al", "algo", "con", "como", "de", "del", "el", "ella", "en", "es", "esta", "este", "estos",
    "la", "las", "lo", "los", "mi", "para", "por", "que", "se", "sin", "su", "sus", "un", "una", "y",
    "yo", "quiero", "quiere", "quieren", "ayudar", "ayudo", "personas", "gente", "porque", "sobre",
    # English
    "a", "an", "and", "are", "as", "at", "be", "because", "by", "for", "from", "his", "i", "in", "is",
    "it", "m", "my", "of", "on", "or", "our", "people", "that", "the", "their", "them", "they", "this",
    "to", "we", "who", "with", "wants", "want", "going", "help", "helps", "how", "last",
    # Portuguese
    "a", "as", "com", "como", "de", "do", "dos", "e", "em", "eu", "o", "os", "para", "por", "que",
    "quero", "quer", "pessoas", "ajudar", "sobre",
}


def _normalize_words(value: str) -> list[str]:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    return [token for token in re.findall(r"[a-z0-9]{3,}", ascii_value) if token not in _STOPWORDS]


def _audience_topic_families(audience: str, *, limit: int = 6) -> tuple[str, ...]:
    """Extract conservative topic phrases from explicit audience text.

    This is not semantic invention. It only compresses words the user already
    supplied so planning never has to treat an entire audience sentence as a
    content topic when no examples/hashtags exist.
    """

    words = _normalize_words(audience)
    if not words:
        return ()

    scored: Counter[str] = Counter()
    for size, bonus in ((3, 3), (2, 2)):
        for index in range(0, len(words) - size + 1):
            phrase_words = words[index : index + size]
            phrase = " ".join(phrase_words)
            # Repeated domain phrases rise naturally; longer phrases get a small
            # specificity bonus without inventing vocabulary.
            scored[phrase] += bonus

    token_counts = Counter(words)
    for token, count in token_counts.items():
        scored[token] += count

    ordered = sorted(
        scored.items(),
        key=lambda item: (-item[1], -len(item[0].split()), -len(item[0]), item[0]),
    )
    selected: list[str] = []
    for phrase, _ in ordered:
        phrase_tokens = set(phrase.split())
        if any(phrase_tokens < set(existing.split()) for existing in selected):
            continue
        selected.append(phrase)
        if len(selected) >= limit:
            break
    return tuple(selected)


class DeterministicProfileAnalyzer:
    """Conservative, provider-free S1 proposal boundary.

    It only derives directly observable traits. A later model adapter may enrich
    proposals behind the same port, but may not silently make them authoritative.
    """

    def propose(self, setup: ProfileSetup) -> ProfileInferenceProposal:
        evidence = tuple(
            InferenceEvidence(
                kind=example.kind,
                sha256=hashlib.sha256(example.text.encode("utf-8")).hexdigest(),
                label=example.label,
                word_count=len(example.text.split()),
            )
            for example in setup.examples
        )
        texts = [example.text.strip() for example in setup.examples]
        word_counts = [len(text.split()) for text in texts]
        average = sum(word_counts) / len(word_counts) if word_counts else 0
        length = "unknown" if not texts else "short" if average < 80 else "medium" if average < 220 else "long"

        hooks: list[str] = []
        if any(text.lstrip().startswith(("¿", "?")) or "?" in text.splitlines()[0] for text in texts if text):
            hooks.append("question")
        if any(re.match(r"^\s*\d+[.):\s]", text) for text in texts):
            hooks.append("numbered")
        if any(text.splitlines() and text.splitlines()[0].isupper() for text in texts):
            hooks.append("uppercase_headline")

        hashtags = []
        for text in texts:
            hashtags.extend(re.findall(r"(?<!\w)#([\w-]{2,40})", text.lower()))
        topics = tuple(dict.fromkeys(hashtags))[:12]
        if not topics:
            topics = _audience_topic_families(setup.audience)

        lower_tail = " ".join(texts[-2:]).lower()
        cta = None
        if any(term in lower_tail for term in ("comenta", "cuéntame", "sígueme", "follow", "comment")):
            cta = "invitation"
        elif texts and any(text.rstrip().endswith("?") for text in texts):
            cta = "question"

        payload = {
            "schema_version": 1,
            "setup_digest": canonical_digest(setup),
            "identity_summary": f"{setup.name}: {setup.audience}",
            "audience_segments": [setup.audience],
            "topic_families": list(topics),
            "hook_tendencies": hooks,
            "caption_length_tendency": length,
            "cta_style": cta,
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "confidence": "explicit_only" if not evidence else "low" if len(evidence) == 1 else "medium",
        }
        return ProfileInferenceProposal(**payload, proposal_digest=canonical_digest(payload))
