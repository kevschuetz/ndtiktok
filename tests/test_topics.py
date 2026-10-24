import json
import os
import sqlite3
from pathlib import Path

import pytest
import yaml

from ndc import topics
from ndc.db import Database
from ndc.topics import TopicError

FIXTURE = Path(__file__).parent / "fixtures" / "topic_seed_small.yaml"


@pytest.fixture
def db():
    return Database(os.environ["NDC_DB"])


def _rows(db):
    conn = db.connect()
    try:
        return {r["working_title"]: r for r in conn.execute("SELECT * FROM topic")}
    finally:
        conn.close()


def _id(db, title_prefix):
    return next(r["id"] for t, r in _rows(db).items() if t.startswith(title_prefix))


def test_matrix_vocab_covers_broader_nd():
    m = topics.load_matrix()
    assert set(m.pillar) == {"challenge_science_help", "strengths", "parents", "men_dads_partners"}
    assert set(m.condition) == {
        "adhd",
        "autism",
        "audhd",
        "dyslexia",
        "dyspraxia_dcd",
        "tourette",
        "dyscalculia",
        "nd_general",
    }
    assert m.condition["adhd"].guideline_layer == "awmf_s3"
    assert m.condition["autism"].guideline_layer == "awmf_s3"
    assert m.condition["tourette"].guideline_layer == "pubmed_reviews"
    assert len(m.domain) == 18
    assert {k for k, v in m.domain.items() if v.sensitive} == {
        "sleep",
        "energy_burnout",
        "late_identification",
    }
    assert all(v.de and v.en for v in m.audience.values())


def test_import_seed_inserts_with_safety(db):
    res = topics.import_seed(db, FIXTURE)
    assert (res.inserted, res.skipped) == (8, 0)
    rows = _rows(db)
    assert len(rows) == 8
    assert {r["status"] for r in rows.values()} == {"proposed"}
    assert {r["language"] for r in rows.values()} == {"de"}
    assert {r["origin"] for r in rows.values()} == {"matrix"}
    assert sum(r["list_tag"] == "blacklist" for r in rows.values()) == 2
    mel = rows["Melatonin und der verschobene Schlafrhythmus"]
    assert mel["safety_status"] == "blocked"
    hits = json.loads(mel["safety_hits_json"])
    assert any(h["rule_id"] == "any.medication_names" for h in hits)
    assert any(h["matched_text"] == "Melatonin" for h in hits)
    assert rows["Morgenroutine mit Bildkarten"]["safety_status"] == "ok"
    assert rows["Morgenroutine mit Bildkarten"]["safety_hits_json"] in (None, "[]")
    assert rows["Wenn der Partner ständig vergisst"]["safety_status"] == "flagged"


def test_import_rejects_unknown_vocab_all_or_nothing(db, tmp_path):
    data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    data["topics"][3]["condition"] = "adhs"
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(TopicError) as exc:
        topics.import_seed(db, bad)
    msg = str(exc.value)
    assert "topics[3]" in msg and "condition" in msg and "adhs" in msg
    assert _rows(db) == {}


def test_import_rejects_unknown_keys(db, tmp_path):
    data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    data["topics"][0]["vibe"] = "x"
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(TopicError):
        topics.import_seed(db, bad)
    assert _rows(db) == {}


def test_import_is_idempotent(db):
    topics.import_seed(db, FIXTURE)
    res = topics.import_seed(db, FIXTURE)
    assert (res.inserted, res.skipped) == (0, 8)
    assert len(_rows(db)) == 8


def test_list_filters_every_dimension(db):
    topics.import_seed(db, FIXTURE)
    got = topics.list_topics(db, {"pillar": "parents", "condition": "adhd"})
    assert [r["working_title"] for r in got] == ["Morgenroutine mit Bildkarten"]
    assert len(topics.list_topics(db, {"domain": "sleep"})) == 1
    assert len(topics.list_topics(db, {"audience": "parents"})) == 2
    assert len(topics.list_topics(db, {"angle": "mechanism_why"})) == 2
    assert len(topics.list_topics(db, {"list_tag": "blacklist"})) == 2
    assert len(topics.list_topics(db, {"status": "proposed"})) == 8
    row = got[0]
    assert row["list_tag"] == "whitelist" and row["safety_status"] == "ok"


def test_list_rejects_unknown_filter_value(db):
    with pytest.raises(TopicError) as exc:
        topics.list_topics(db, {"pillar": "foo"})
    assert "strengths" in str(exc.value)


def test_add_topic_validates_and_checks(db):
    with pytest.raises(TopicError):
        topics.add_topic(
            db,
            pillar="parents",
            condition="adhs",
            domain="sleep",
            audience="parents",
            angle="mechanism_why",
            working_title="X",
            list_tag="whitelist",
            source_likely="yes",
            language="de",
        )
    new_id = topics.add_topic(
        db,
        pillar="parents",
        condition="adhd",
        domain="sleep",
        audience="parents",
        angle="mechanism_why",
        working_title="Melatonin für Kinder",
        list_tag="whitelist",
        source_likely="yes",
        language="de",
    )
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM topic WHERE id = ?", (new_id,)).fetchone()
    finally:
        conn.close()
    assert row["safety_status"] == "blocked"
    assert "any.medication_names" in row["safety_hits_json"]


def test_add_topic_without_language_checks_both(db):
    new_id = topics.add_topic(
        db,
        pillar="parents",
        condition="adhd",
        domain="sleep",
        audience="parents",
        angle="mechanism_why",
        working_title="Kids and melatonin",
        list_tag="whitelist",
        source_likely="yes",
    )
    conn = db.connect()
    try:
        row = conn.execute("SELECT safety_status FROM topic WHERE id = ?", (new_id,)).fetchone()
    finally:
        conn.close()
    assert row["safety_status"] == "blocked"


def test_no_anthropic_import():
    src = Path(topics.__file__).read_text(encoding="utf-8")
    assert "anthropic" not in src


def test_unique_constraint_still_holds(db):
    topics.import_seed(db, FIXTURE)
    conn = db.connect()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO topic (pillar, condition, domain, audience, angle, language, "
                "working_title, list_tag, source_likely) VALUES "
                "('parents','adhd','sleep','parents','mechanism_why','de',"
                "'Morgenroutine mit Bildkarten','whitelist','yes')"
            )
    finally:
        conn.close()


# ---------------------------------------------------------------- task 2: review / select / stats
# fixture ids: 1 Zeit, 2 Melatonin (blocked), 3 Interessen, 4 Legasthenie, 5 Morgenroutine,
# 6 Checkliste (blacklist, blocked), 7 Partner (flagged), 8 Männer (blacklist, ok)


def _status(db, topic_id):
    conn = db.connect()
    try:
        return conn.execute("SELECT * FROM topic WHERE id = ?", (topic_id,)).fetchone()
    finally:
        conn.close()


def test_keep_moves_proposed_to_backlog(db):
    topics.import_seed(db, FIXTURE)
    assert topics.keep(db, [3, 5]) == 2
    for i in (3, 5):
        row = _status(db, i)
        assert row["status"] == "backlog" and row["decided_at"]
    with pytest.raises(TopicError):
        topics.keep(db, [3])
    # all-or-nothing: an invalid id leaves the valid one untouched
    with pytest.raises(TopicError):
        topics.keep(db, [1, 99])
    assert _status(db, 1)["status"] == "proposed"


def test_kill_requires_reason(db):
    topics.import_seed(db, FIXTURE)
    with pytest.raises(TopicError):
        topics.kill(db, 4, "kurz")
    assert _status(db, 4)["status"] == "proposed"
    topics.kill(db, 4, "zu nah an Diagnosefrage")
    row = _status(db, 4)
    assert row["status"] == "rejected"
    assert row["decided_reason"] == "zu nah an Diagnosefrage"
    assert row["decided_at"]
    with pytest.raises(TopicError):
        topics.kill(db, 4, "nochmal killen")


def test_select_refuses_blacklist_and_blocked(db):
    topics.import_seed(db, FIXTURE)
    topics.keep(db, [2, 3, 8])
    with pytest.raises(TopicError) as exc:
        topics.select(db, 2)
    assert "blocked" in str(exc.value)
    with pytest.raises(TopicError) as exc:
        topics.select(db, 8)
    assert "blacklist" in str(exc.value)
    assert _status(db, 2)["status"] == "backlog"
    assert _status(db, 8)["status"] == "backlog"
    with pytest.raises(TopicError):
        topics.select(db, 1)  # proposed, not backlog
    topics.select(db, 3)
    assert _status(db, 3)["status"] == "selected"


def test_select_guard_holds_against_a_tampered_row(db):
    """Even if the status check passes, the UPDATE itself re-checks tag and safety."""
    topics.import_seed(db, FIXTURE)
    topics.keep(db, [6])
    with pytest.raises(TopicError):
        topics.select(db, 6)
    assert _status(db, 6)["status"] == "backlog"


def test_stats_per_pillar(db):
    topics.import_seed(db, FIXTURE)
    topics.keep(db, [1, 3, 7, 8])
    topics.kill(db, 4, "kein guter Fit")
    st = topics.stats(db)
    assert st["target"] == 7
    p = st["pillars"]
    assert set(p) == {"challenge_science_help", "strengths", "parents", "men_dads_partners"}
    assert p["challenge_science_help"]["counts"] == {"backlog": 1, "proposed": 1}
    assert p["strengths"]["counts"] == {"backlog": 1, "rejected": 1}
    assert p["challenge_science_help"]["kept_safe_whitelist"] == 1
    assert p["strengths"]["kept_safe_whitelist"] == 1
    assert p["parents"]["kept_safe_whitelist"] == 0
    assert p["men_dads_partners"]["kept_safe_whitelist"] == 1  # 7 flagged counts, 8 blacklist not
    assert all(v["below_target"] for v in p.values())
