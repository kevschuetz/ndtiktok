"""Hashtag harvest from competitor_post descriptions (MKT-03, plan 01-14)."""

import yaml
from scan_seed import seed_account

from ndc.scan import hashtags


def _set_views(db, handle, views):
    conn = db.connect()
    try:
        conn.execute(
            "UPDATE competitor_post SET views = ? WHERE account_id ="
            " (SELECT id FROM competitor_account WHERE handle = ?)",
            (views, handle),
        )
    finally:
        conn.close()


def _seed(db):
    seed_account(
        db,
        "a1",
        posts=[
            ("p1", "Alltag #ADHS #ADHSMänner #Ritalin", None),
            ("p2", "Neu #adhs #Neurodivergent", None),
        ],
    )
    seed_account(
        db,
        "a2",
        posts=[("p3", "#ADHS und #adhsmänner #ActuallyAutistic #Diagnose", None)],
    )
    seed_account(db, "e1", lang="en", posts=[("p4", "#ADHD #adhs", None)])
    _set_views(db, "a1", 1000)
    _set_views(db, "a2", 3000)


def _by_tag(stats):
    return {s.tag: s for s in stats}


def test_harvest_counts_distinct_accounts_and_merges_case(db):
    _seed(db)
    stats = _by_tag(hashtags.harvest(db, "de"))
    assert stats["#adhs"].n_accounts == 2  # en account ignored
    assert stats["#adhs"].n_posts == 3
    assert stats["#adhsmänner"].n_accounts == 2  # umlaut matched, case merged
    assert stats["#adhsmänner"].display == "#ADHSMänner"
    assert "#adhd" not in stats


def test_harvest_mid_tier_median_views(db):
    _seed(db)
    stats = _by_tag(hashtags.harvest(db, "de"))
    # posts carrying #adhs: 1000, 1000, 3000 -> median 1000
    assert stats["#adhs"].mid_median_views == 1000
    assert stats["#adhsmänner"].mid_median_views == 2000


def test_safety_and_community_exclusions(db):
    _seed(db)
    stats = _by_tag(hashtags.harvest(db, "de"))
    assert stats["#ritalin"].excluded
    assert "any.medication_names" in stats["#ritalin"].exclusion_reason
    assert stats["#diagnose"].excluded
    assert stats["#actuallyautistic"].excluded
    assert stats["#actuallyautistic"].exclusion_reason == "community_self_id"
    assert not stats["#adhs"].excluded


def test_harvest_ignores_tags_inside_words(db):
    seed_account(db, "a3", posts=[("p9", "mail me a@b.de #ADHS#Autismus", None)])
    tags = {s.tag for s in hashtags.harvest(db, "de")}
    assert tags == {"#adhs", "#autismus"}


def test_write_harvest_yaml(db, tmp_path):
    _seed(db)
    out = tmp_path / "h.yaml"
    hashtags.write_harvest(hashtags.harvest(db, "de"), out, "de")
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["language"] == "de"
    tags = {t["tag"]: t for t in data["tags"]}
    assert tags["#adhs"]["n_accounts"] == 2
    assert tags["#ritalin"]["excluded"] is True
