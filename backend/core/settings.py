import os
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

VALID_LANGUAGES = {"es", "en", "pt"}
_WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
LEGACY_WORKSPACE_ID = "legacy-default"


@dataclass(frozen=True)
class ApplicationSettings:
    """Single authority for all configuration. Validated at startup."""

    app_default_language: str
    language_min_confidence: float
    language_min_margin: float
    image_render_enabled: bool
    app_workspace_id: str

    @classmethod
    def load(cls) -> "ApplicationSettings":
        """Load and validate all settings from environment. Raises ValueError on invalid config."""
        lang = os.environ.get("APP_DEFAULT_LANGUAGE", "").strip()
        if not lang:
            raise ValueError(
                "APP_DEFAULT_LANGUAGE is required. Set it to one of: es, en, pt"
            )
        if lang not in VALID_LANGUAGES:
            raise ValueError(
                f"Invalid APP_DEFAULT_LANGUAGE: {lang}. Must be one of: {sorted(VALID_LANGUAGES)}"
            )

        try:
            min_confidence = float(os.environ.get("LANGUAGE_MIN_CONFIDENCE", "0.6"))
        except ValueError:
            raise ValueError("LANGUAGE_MIN_CONFIDENCE must be a float (e.g. 0.6)")

        try:
            min_margin = float(os.environ.get("LANGUAGE_MIN_MARGIN", "0.2"))
        except ValueError:
            raise ValueError("LANGUAGE_MIN_MARGIN must be a float (e.g. 0.2)")

        image_render_enabled_str = os.environ.get("IMAGE_RENDER_ENABLED", "true").lower()
        image_render_enabled = image_render_enabled_str in ("true", "1", "yes")

        raw_workspace_id = os.environ.get("APP_WORKSPACE_ID")
        workspace_id = LEGACY_WORKSPACE_ID if raw_workspace_id is None else raw_workspace_id.strip()
        if not workspace_id:
            raise ValueError("APP_WORKSPACE_ID must not be blank when explicitly configured")
        if not _WORKSPACE_ID_RE.fullmatch(workspace_id):
            raise ValueError(
                "APP_WORKSPACE_ID must be 1-64 characters using letters, numbers, '.', '_' or '-'"
            )

        return cls(
            app_default_language=lang,
            language_min_confidence=min_confidence,
            language_min_margin=min_margin,
            image_render_enabled=image_render_enabled,
            app_workspace_id=workspace_id,
        )
