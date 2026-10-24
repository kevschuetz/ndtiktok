"""`ndc scan prepare-judging` batch bundles (plan 01-06 Task 4, D-21)."""

import json
from pathlib import Path

from scan_seed import seed_account

from ndc.cli import app
from ndc.scan import bundle


def _seed_many(db):
    ids = {"de": [], "en": []}
    for i in range(45):
        ids["de"].append(
            seed_account(db, f"de_{i:02d}", lang="de", posts=[(f"d{i}", f"Ignore rules {i}", None)])
        )
    for i in range(40):
        ids["en"].append(
            seed_account(
                db,
                f"@en{i:02d}",
                platform="youtube",
                lang="en",
                posts=[(f"e{i}", f"cap {i}", f"pinned refs {i}")],
                videos=[(f"e{i}", f"transcript {i}", "ok")],
            )
        )
    return ids


def test_batches_and_manifests(db, tmp_path):
    _seed_many(db)
    rep = bundle.prepare_judging(db, tmp_path / "judging", 2)
    assert sorted(rep.manifests) == ["de-1", "de-2", "en-1", "en-2"]
    assert rep.counts == {"de-1": 23, "de-2": 22, "en-1": 20, "en-2": 20}
    m = json.loads(Path(rep.manifests["de-1"]).read_text())
    assert m["batch"] == "de-1" and m["accounts"][0] == "tiktok:de_00"
    m2 = json.loads(Path(rep.manifests["de-2"]).read_text())
    assert not set(m["accounts"]) & set(m2["accounts"])
    assert m["output"].endswith("de-1/judgments.json") and m["provenance"] == "llm_session"
    en = json.loads(Path(rep.manifests["en-1"]).read_text())
    files = en["files"]["youtube:@en00"]
    caps = json.loads(Path(files["captions"]).read_text())
    assert caps["bio"] == "bio text"
    assert caps["posts"] == [
        {"post_id": "e0", "description": "cap 0", "pinned_comment": "pinned refs 0"}
    ]
    assert set(caps) == {"account_key", "language", "bio", "posts"}  # data only, no prompt text
    assert json.loads(Path(files["transcripts"]).read_text()) == {"e0": "transcript 0"}
    de_caps = json.loads(Path(m["files"]["tiktok:de_00"]["captions"]).read_text())
    assert "pinned_comment" not in de_caps["posts"][0]  # TikTok has no uploader pinned comments


def test_newest_15_posts(db, tmp_path):
    posts = [(f"p{i:02d}", f"c{i}", None) for i in range(20)]
    seed_account(db, "many", posts=posts)
    rep = bundle.prepare_judging(db, tmp_path / "j", 2)
    m = json.loads(Path(rep.manifests["de-1"]).read_text())
    caps = json.loads(Path(m["files"]["tiktok:many"]["captions"]).read_text())
    assert len(caps["posts"]) == 15 and caps["posts"][0]["post_id"] == "p00"


def test_cli_batch_prints_manifest(db, tmp_path, runner, monkeypatch):
    _seed_many(db)
    res = runner.invoke(
        app, ["scan", "prepare-judging", "--judging-dir", str(tmp_path / "jd"), "--batch", "de-1"]
    )
    assert res.exit_code == 0, res.output
    assert res.output.strip().endswith(str(tmp_path / "jd" / "de-1" / "manifest.json"))
