import sqlite3

import pytest

from ndc.checks.engine import check, record_override
from ndc.config import db_path
from ndc.db import Database

WARN_TEXT = "Er leidet an ADHS und nennt es eine Superkraft."
BLOCK_TEXT = "Sie gilt als hochfunktional."


@pytest.fixture
def db():
    return Database(db_path())


def _warn_ids(res):
    return sorted({f.rule_id for f in res.findings if f.tier == "warn"})


def test_overrides_turn_warns_ok(db):
    res = check(WARN_TEXT, "de", "script", db=db)
    assert res.status == "needs_override"
    ids = _warn_ids(res)
    assert ids
    for rid in ids:
        record_override(db, WARN_TEXT, rid, "script", "Zitat einer Betroffenen")
    res = check(WARN_TEXT, "de", "script", db=db)
    assert res.status == "ok"
    assert res.overridden_rule_ids == ids


def test_override_bound_to_text_hash(db):
    for rid in _warn_ids(check(WARN_TEXT, "de", "script")):
        record_override(db, WARN_TEXT, rid, "script", "Zitat einer Betroffenen")
    edited = WARN_TEXT.replace("Er", "Sie", 1)
    res = check(edited, "de", "script", db=db)
    assert res.status == "needs_override"
    assert res.overridden_rule_ids == []


def test_block_rule_cannot_be_overridden(db):
    with pytest.raises(ValueError):
        record_override(db, BLOCK_TEXT, "de.hochfunktional", "script", "bitte durchlassen")
    with pytest.raises(ValueError):
        record_override(db, "Habe ich ADHS?", "de.diagnosis_question", "topic", "bitte durchlassen")
    conn = db.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM check_override").fetchone()[0] == 0
    finally:
        conn.close()
    assert check(BLOCK_TEXT, "de", "script", db=db).status == "blocked"


def test_short_reason_rejected(db):
    with pytest.raises(ValueError):
        record_override(db, WARN_TEXT, "de.leiden_an", "script", "ok")


def test_unknown_rule_rejected(db):
    with pytest.raises(ValueError):
        record_override(db, WARN_TEXT, "de.nope", "script", "irgendein Grund")


def test_db_check_constraint_enforces_reason(db):
    conn = db.connect()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO check_override (text_sha256, rule_id, level, reason, "
                "terminology_version, created_at) "
                "VALUES ('x','de.leiden_an','script','  ab ',1,'t')"
            )
    finally:
        conn.close()


def test_override_records_version_and_level(db):
    record_override(db, WARN_TEXT, "de.leiden_an", "claim", "Zitat einer Betroffenen")
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT level, terminology_version, reason FROM check_override"
        ).fetchone()
    finally:
        conn.close()
    assert tuple(row) == ("claim", 1, "Zitat einer Betroffenen")
