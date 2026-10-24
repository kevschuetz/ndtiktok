"""Table-driven tests for the pure language decision rule (D-20)."""

from pathlib import Path

import pytest

from ndc.scan.decide import AccountRow, decide, load_rule

REPO_RULE = Path(__file__).resolve().parents[2] / "config" / "decision_rule.yaml"


@pytest.fixture(scope="module")
def rule():
    return load_rule(REPO_RULE)


def acct(
    handle,
    lang,
    *,
    platform="tiktok",
    followers=50_000,
    reach=10_000.0,
    n=15,
    score=0,
    face="face",
    voice="female",
):
    return AccountRow(
        handle=handle,
        language=lang,
        platform=platform,
        followers=followers,
        reach_median=reach,
        n_reach_posts=n,
        source_citing_score=score,
        face=face,
        voice_gender=voice,
    )


def build(n_mid_de=10, n_mid_en=10, r_de=1_000.0, r_en=8_000.0, n_de=0, s_de=0, s_en=0):
    """Mid-tier TikTok accounts with uniform reach so medians are exact, plus extra sourced
    micro-tier accounts (not in reach metrics) to reach the requested N/S counts."""
    rows = [acct(f"de{i}", "de", reach=r_de) for i in range(n_mid_de)]
    rows += [acct(f"en{i}", "en", reach=r_en) for i in range(n_mid_en)]
    for i in range(n_de):
        slot = i < s_de
        rows.append(
            acct(
                f"desrc{i}",
                "de",
                followers=5_000,
                score=2,
                face="faceless" if slot else "face",
                voice="male" if slot else "female",
            )
        )
    for i in range(s_en):
        rows.append(
            acct(f"ensrc{i}", "en", followers=5_000, score=3, face="faceless", voice="male")
        )
    return rows


CASES = [
    # id, kwargs, verdict, row, inconclusive
    ("V", dict(n_mid_de=7, n_mid_en=12), "de", "V", True),
    ("V_en_short", dict(n_mid_de=12, n_mid_en=7, r_en=50_000), "de", "V", True),
    ("R1", dict(n_de=3, r_en=8_000), "de", "R1", False),
    ("R2", dict(n_de=3, r_en=16_000), "en", "R2", False),
    ("R3", dict(n_de=9, s_de=1, s_en=0, r_en=5_000), "en", "R3", False),
    ("R4", dict(n_de=6, r_en=12_000), "de", "R4", True),
    ("R1_boundary_Q10_N4", dict(n_de=4, r_en=10_000), "de", "R1", False),
    ("Q15_not_R2", dict(n_de=6, r_en=15_000), "de", "R4", True),
    ("R3_blocked_by_S_EN", dict(n_de=9, s_de=1, s_en=1, r_en=5_000), "de", "R4", True),
]


@pytest.mark.parametrize("cid,kw,verdict,row,inconc", CASES, ids=[c[0] for c in CASES])
def test_rule_rows(rule, cid, kw, verdict, row, inconc):
    res = decide(build(**kw), rule)
    assert res.verdict == verdict
    assert res.matched_row == row
    assert res.inconclusive is inconc


def test_metrics_reported(rule):
    res = decide(build(n_de=3, r_en=8_000), rule)
    m = res.metrics
    assert m["R_DE"] == 1_000 and m["R_EN"] == 8_000 and m["Q"] == pytest.approx(8.0)
    assert m["n_mid_de"] == 10 and m["n_mid_en"] == 10
    assert m["N_DE"] == 3 and m["N_EN"] == 0 and m["S_DE"] == 0 and m["S_EN"] == 0
    assert len(res.rule_sha256) == 64


def test_youtube_never_changes_q(rule):
    base = build(n_de=3, r_en=8_000)
    before = decide(base, rule)
    yt = [
        acct(f"yt{i}", "en", platform="youtube", reach=9_000_000.0, followers=50_000)
        for i in range(20)
    ]
    after = decide(base + yt, rule)
    assert after.metrics["Q"] == before.metrics["Q"]
    assert after.verdict == before.verdict and after.matched_row == before.matched_row
    assert after.metrics["youtube_R_EN"] == 9_000_000
    assert after.metrics["youtube_R_DE"] is None


def test_thin_reach_excluded_but_counted_for_sourcing(rule):
    rows = build(n_mid_de=8, n_de=0, r_en=8_000)
    rows.append(acct("dethin", "de", reach=99_999.0, n=7, score=2))
    res = decide(rows, rule)
    assert res.metrics["n_mid_de"] == 8
    assert res.metrics["R_DE"] == 1_000
    assert res.metrics["N_DE"] == 1


def test_unknown_face_or_voice_never_in_slot(rule):
    rows = build(n_de=0, r_en=8_000)
    rows.append(acct("u1", "de", score=3, face="unknown", voice="male", followers=5_000))
    rows.append(acct("u2", "de", score=3, face="faceless", voice="unknown", followers=5_000))
    rows.append(acct("u3", "de", score=3, face="mixed", voice="male", followers=5_000))
    res = decide(rows, rule)
    assert res.metrics["N_DE"] == 3
    assert res.metrics["S_DE"] == 0


def test_same_handle_counts_once(rule):
    rows = build(n_de=0, r_en=8_000)
    rows.append(acct("Creator", "de", score=2, followers=5_000))
    rows.append(acct("creator", "de", platform="youtube", score=3, followers=5_000))
    assert decide(rows, rule).metrics["N_DE"] == 1


def test_under_1000_followers_excluded(rule):
    rows = build(n_de=0, r_en=8_000)
    rows.append(acct("tiny", "de", score=3, followers=500))
    assert decide(rows, rule).metrics["N_DE"] == 0


def test_verdict_always_single_language(rule):
    for _cid, kw, *_ in CASES:
        assert decide(build(**kw), rule).verdict in ("de", "en")
    assert decide([], rule).verdict == "de"
