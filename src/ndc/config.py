"""Path resolution and .env loading. Never logs secret values."""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"
DEFAULT_DB = "/data/ndc.db"


def config_dir() -> Path:
    env = os.environ.get("NDC_CONFIG_DIR")
    if env:
        return Path(env)
    app_cfg = Path("/app/config")
    return app_cfg if app_cfg.exists() else REPO_CONFIG


def db_path() -> str:
    return os.environ.get("NDC_DB") or DEFAULT_DB


def load_env() -> None:
    """Load .env without overriding variables already set in the environment.

    NDC_ENV_FILE selects the file; default is ./.env in the working directory.
    """
    path = os.environ.get("NDC_ENV_FILE") or str(Path.cwd() / ".env")
    if Path(path).is_file():
        load_dotenv(path, override=False)
