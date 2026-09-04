import hashlib
import re

from domain.profiles.models import (
    InferenceEvidence,
    ProfileInferenceProposal,
    ProfileSetup,
    canonical_digest,
)


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
