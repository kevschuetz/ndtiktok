from pathlib import Path

import pytest
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Every test gets its own tmp DB; nothing ever touches /data/ndc.db."""
    monkeypatch.setenv("NDC_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("NDC_CONFIG_DIR", str(REPO_ROOT / "config"))
    monkeypatch.setenv("NDC_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    yield


@pytest.fixture
def runner():
    return CliRunner()
