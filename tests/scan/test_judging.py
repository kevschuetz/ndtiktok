"""In-session judgment import with the evidence substring guard (plan 01-06 Task 2, D-21)."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from scan_seed import obs_rows, seed_account, sheet_row

from ndc.cli import app
from ndc.scan import judging

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "scan" / "judgments_sample.json"

ALPHA_POSTS = [
    ("a1", "Heute: laut S3-Leitlinie ADHS ist das so.", None),
    ("a2", "Barkley sagt,  das stimmt.", None),
    ("a3", "Eine Studie der Uni Bonn zeigt", None),
    ("a4", "Studien zeigen viel", None),
    ("a5", "Kein Beleg", "Quellen: Faraone et al. 2021, doi:10.1/x"),
]
ALPHA_VIDEOS = [("a1", "also laut Leitlinie ist das", "ok"), ("a2", "", "ok")]


def _seed_both(db):
    a = seed_account(db, "alpha_adhs", posts=ALPHA_POSTS, videos=ALPHA_VIDEOS)
    b = seed_account(
        db, "@betachannel", platform="youtube", lang="en", posts=[("b1", "science says hi", None)]
    )
    return a, b


def _sample():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _write(tmp_path, data, name="j.json"):
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_sample_validates():
    data = _sample()
    js = [judging.AccountJudgment.model_validate(j) for j in data["judgments"]]
    assert [j.account_key for j in js] == ["tiktok:alpha_adhs", "youtube:@betachannel"]


def test_unknown_key_or_bad_level_rejects_whole_file(db, tmp_path):
    a, b = _seed_both(db)
    data = _sample()
    data["judgments"][1]["bogus"] = 1
    with pytest.raises(judging.JudgmentFileError) as exc:
        judging.import_judgments(db, _write(tmp_path, data))
    assert "youtube:@betachannel" in str(exc.value) and "bogus" in str(exc.value)
    assert obs_rows(db, a) == [] and obs_rows(db, b) == []

    data = _sample()
    data["judgments"][0]["posts"][0]["level"] = 4
    with pytest.raises(judging.JudgmentFileError) as exc:
        judging.import_judgments(db, _write(tmp_path, data))
    assert "tiktok:alpha_adhs" in str(exc.value) and "level" in str(exc.value)
    assert obs_rows(db, a) == []


def test_missing_confidence_key_fails():
    j = copy.deepcopy(_sample()["judgments"][0])
    del j["confidence"]["format"]
    with pytest.raises(ValidationError):
        judging.AccountJudgment.model_validate(j)


def test_unknown_account_rejects_file(db, tmp_path):
    seed_account(db, "alpha_adhs", posts=ALPHA_POSTS, videos=ALPHA_VIDEOS)
    with pytest.raises(judging.JudgmentFileError, match="youtube:@betachannel"):
        judging.import_judgments(db, _write(tmp_path, _sample()))


def test_evidence_guard_caption_pinned_speech(db):
    aid = seed_account(db, "alpha_adhs", posts=ALPHA_POSTS, videos=ALPHA_VIDEOS)
    conn = db.connect()
    try:
        c = judging.Citation
        cases = [
            (c(source="caption", post_id="a1", level=2, evidence="laut S3-Leitlinie ADHS"), 2),
            (c(source="caption", post_id="a2", level=2, evidence="Barkley sagt, das"), 2),
            (c(source="caption", post_id="a1", level=2, evidence="laut AWMF-Leitlinie"), 0),
            (c(source="caption", post_id="a1", level=1, evidence=None), 0),
            (c(source="caption", post_id="zz", level=1, evidence="Heute"), 0),
            (c(source="pinned_comment", post_id="a5", level=3, evidence="Faraone et al. 2021"), 3),
            (c(source="pinned_comment", post_id="a1", level=3, evidence="Faraone"), 0),
            (c(source="speech", video_id="a1", level=2, evidence="laut Leitlinie"), 2),
            (c(source="speech", video_id="a1", level=2, evidence="laut Studie"), 0),
            (c(source="onscreen", video_id="a2", level=3, evidence="Quelle: X"), 3),
            (c(source="caption", post_id="a4", level=0, evidence=None), 0),
        ]
        for cit, expected in cases:
            out = judging.apply_evidence_guard(conn, aid, cit)
            assert out.level == expected, cit
            if cit.level > 0 and expected == 0:
                assert out.guard_result == "downgraded"
            else:
                assert out.guard_result == "kept"
    finally:
        conn.close()


@pytest.mark.parametrize(
    "levels,expected",
    [([3, 2, 2, 2, 0], 2), ([3, 3, 1, 0, 0], 1), ([3, 3, 3], 3), ([0, 0], 0), ([1, 1], 0)],
)
def test_text_level(levels, expected):
    assert judging.account_level(levels, judging.TEXT_MIN_POSTS) == expected


def test_video_level():
    assert judging.account_level([2, 3], judging.VIDEO_MIN_VIDEOS) == 2
    assert judging.account_level([3, 0, 1], judging.VIDEO_MIN_VIDEOS) == 1


def test_import_writes_llm_session_obs_and_sheet(db, tmp_path):
    a, b = _seed_both(db)
    rep = judging.import_judgments(db, FIXTURE)
    assert rep.accounts == 2 and rep.downgraded == 0
    by_field = {r["field"]: r for r in obs_rows(db, a) if r["provenance"] == "llm_session"}
    for f in (
        "source_text_level",
        "source_video_level",
        "face",
        "format",
        "pillars",
        "audiences",
        "monetization_signals",
        "hedging_or_diagnostic",
    ):
        assert f in by_field, f
        assert by_field[f]["method"] == "in-session judgment, rubric v1"
    assert by_field["source_text_level"]["value"] == "2"
    assert by_field["source_video_level"]["value"] == "2"
    assert by_field["source_text_level"]["confidence"] == "high"
    assert by_field["format"]["confidence"] == "medium"
    assert by_field["pillars"]["value"] == "challenge_science_help,parents"
    row = sheet_row(db, a)
    assert row["source_citing_score"] == 2 and row["face"] == "faceless"
    assert row["face_provenance"] == "llm_session"
    assert row["needs_operator_check"] == "false"
    brow = sheet_row(db, b)
    assert brow["source_text_level"] == "0" and brow["source_video_level"] is None


def test_reimport_replaces_not_duplicates(db, tmp_path):
    a, _ = _seed_both(db)
    judging.import_judgments(db, FIXTURE)
    n1 = len([r for r in obs_rows(db, a) if r["provenance"] == "llm_session"])
    judging.import_judgments(db, FIXTURE)
    n2 = len([r for r in obs_rows(db, a) if r["provenance"] == "llm_session"])
    assert n1 == n2
    conn = db.connect()
    try:
        n_cit = conn.execute(
            "SELECT COUNT(*) FROM competitor_post_citing WHERE account_id = ?", (a,)
        ).fetchone()[0]
    finally:
        conn.close()
    assert n_cit == 8  # 6 post citations + 1 speech + 1 onscreen


def test_hallucinated_evidence_downgrades_and_queues(db, tmp_path):
    a, _ = _seed_both(db)
    data = _sample()
    for p in data["judgments"][0]["posts"][:3]:
        p["evidence"] = "made up quote"
    rep = judging.import_judgments(db, _write(tmp_path, data))
    assert rep.downgraded == 3
    row = sheet_row(db, a)
    assert row["source_text_level"] == "0"  # a1-a3 -> 0; a4 1, a5 3 -> only 2 posts >= 1
    assert row["needs_operator_check"] == "true"


def test_cli_import(db, tmp_path, runner):
    _seed_both(db)
    res = runner.invoke(app, ["scan", "import-judgments", str(FIXTURE)])
    assert res.exit_code == 0, res.output
    assert "imported 2" in res.output
    bad = _sample()
    bad["judgments"][0]["face"] = "maybe"
    res = runner.invoke(app, ["scan", "import-judgments", str(_write(tmp_path, bad))])
    assert res.exit_code == 2


def test_no_anthropic_anywhere():
    """D-21: no anthropic import or dependency (the env status line in ndc/cli.py only reports
    whether ANTHROPIC_API_KEY is set, for Phase 2)."""
    import re

    root = Path(__file__).resolve().parents[2]
    pat = re.compile(r"^\s*(import|from)\s+anthropic\b", re.M)
    for p in (root / "src").rglob("*.py"):
        assert not pat.search(p.read_text(encoding="utf-8")), p
    assert "anthropic" not in (root / "pyproject.toml").read_text(encoding="utf-8").lower()
