"""Quiet-hours guard 00:15-06:00 UTC (D-16, Pitfall 8)."""

import os
from datetime import UTC, datetime

import pytest

from ndc.cli import app
from ndc.db import Database
from ndc.scan import quiet_hours, tiktok


def _at(h, m):
    return lambda: datetime(2026, 10, 24, h, m, tzinfo=UTC)


@pytest.mark.parametrize(
    "h,m,quiet",
    [
        (0, 14, False),
        (0, 15, True),
        (0, 20, True),
        (5, 59, True),
        (6, 0, False),
        (6, 1, False),
        (21, 0, False),
    ],
)
def test_window(h, m, quiet):
    assert quiet_hours.in_quiet_hours(_at(h, m)()) is quiet


def test_wrapping_window():
    assert quiet_hours.in_quiet_hours(_at(23, 30)(), "23:00", "02:00")
    assert not quiet_hours.in_quiet_hours(_at(12, 0)(), "23:00", "02:00")


@pytest.fixture
def stub(monkeypatch):
    calls = []
    monkeypatch.setattr(tiktok, "fetch_profile", lambda h: calls.append(h) or {"followers": 2000})
    return calls


def test_fetch_refused_in_quiet_hours(monkeypatch, runner, stub):
    monkeypatch.setattr(quiet_hours, "utcnow", _at(0, 20))
    res = runner.invoke(app, ["scan", "fetch", "--stage", "profile"])
    assert res.exit_code == 4, res.output
    conn = Database(os.environ["NDC_DB"]).connect()
    assert conn.execute("SELECT count(*) FROM scan_run").fetchone()[0] == 0


def test_force_overrides_and_logs(monkeypatch, runner, stub):
    monkeypatch.setattr(quiet_hours, "utcnow", _at(0, 20))
    res = runner.invoke(app, ["scan", "fetch", "--stage", "profile", "--force"])
    assert res.exit_code == 0, res.output
    conn = Database(os.environ["NDC_DB"]).connect()
    notes = conn.execute("SELECT notes FROM scan_run").fetchone()[0]
    assert "quiet_hours_override" in notes


def test_after_window_proceeds(monkeypatch, runner, stub):
    monkeypatch.setattr(quiet_hours, "utcnow", _at(6, 1))
    res = runner.invoke(app, ["scan", "fetch", "--stage", "profile"])
    assert res.exit_code == 0, res.output
    conn = Database(os.environ["NDC_DB"]).connect()
    run = conn.execute("SELECT notes FROM scan_run").fetchone()
    assert run[0] is None
