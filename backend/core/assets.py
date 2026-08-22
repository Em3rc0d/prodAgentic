import os
from pathlib import Path


ASSET_ROOT_ENV = "PRODAGENTIC_ASSET_ROOT"
DEFAULT_ASSET_ROOT = "static/assets"


def get_asset_root() -> Path:
    """Return the single filesystem authority for persisted product assets."""
    configured = os.environ.get(ASSET_ROOT_ENV, "").strip()
    return Path(configured or DEFAULT_ASSET_ROOT).expanduser().resolve()


def prepare_asset_root() -> Path:
    """Create the shared asset tree and return its resolved root path."""
    root = get_asset_root()
    (root / "renders").mkdir(parents=True, exist_ok=True)
    return root


def get_render_storage_dir() -> Path:
    return prepare_asset_root() / "renders"
