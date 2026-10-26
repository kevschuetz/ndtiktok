import pytest
from review_helpers import row, sha_of, verify_with

from ndc.review import store

FRAMING = dict(kind="framing", verdict="not_applicable")


def _ok_rows():
    return [row(0, **FRAMING), row(1), row(2), row(3, **FRAMING)]


def test_approve_refused_when_blocked_and_nothing_written(db, version):
    verify_with(
        db, version, [row(0, **FRAMING), row(1, verdict="unsupported"), row(2), row(3, **FRAMING)]
    )
    with pytest.raises(store.ReviewRefused, match="nicht freigebbar"):
        store.decide(db, sha_of(db, version), "approved")
    conn = db.connect()
    assert conn.execute("SELECT count(*) FROM review").fetchone()[0] == 0
    conn.close()


def test_approve_and_latest_decision(db, version):
    verify_with(db, version, _ok_rows())
    sha = sha_of(db, version)
    store.decide(db, sha, "approved")
    assert store.latest_decision(db, sha)["decision"] == "approved"
    store.decide(db, sha, "changes_requested", note="Hook schärfer")
    assert store.latest_decision(db, sha)["decision"] == "changes_requested"


@pytest.mark.parametrize("decision", ["rejected", "changes_requested"])
def test_note_required(db, version, decision):
    verify_with(db, version, _ok_rows())
    with pytest.raises(store.ReviewRefused, match="begründen"):
        store.decide(db, sha_of(db, version), decision, note="kurz")


def test_ack_only_for_needs_ack(db, version):
    verify_with(db, version, _ok_rows())
    with pytest.raises(store.ReviewRefused, match="braucht keine"):
        store.ack(db, sha_of(db, version), 1)


def test_unknown_sha(db, version):
    with pytest.raises(store.ReviewRefused):
        store.decide(db, "0" * 64, "approved")


def test_cli_show_ack_decide(runner, db, version):
    from ndc.cli import app

    verify_with(
        db, version, [row(0, **FRAMING), row(1, verdict="overstated"), row(2), row(3, **FRAMING)]
    )
    sha = sha_of(db, version)
    r = runner.invoke(app, ["review", "show", sha[:12]])
    assert r.exit_code == 0 and "Bestätigungen offen" in r.output and "ÜBERZOGEN" in r.output
    r = runner.invoke(app, ["review", "decide", sha[:12], "approved"])
    assert r.exit_code == 1 and "nicht freigebbar" in r.output
    assert runner.invoke(app, ["review", "ack", sha[:12], "1"]).exit_code == 0
    r = runner.invoke(app, ["review", "decide", sha[:12], "approved"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["review", "status"])
    assert "approved" in r.output


def test_render_sources_after_approval(db, version):
    from ndc.script import sources_list as sl

    verify_with(db, version, _ok_rows())
    sha = sha_of(db, version)
    with pytest.raises(sl.NotApproved):
        sl.render(db, sha)
    store.decide(db, sha, "approved")
    cap = sl.render(db, sha, "caption")[0]
    assert cap.splitlines() == [
        "Quellen:",
        "Soler-Gutiérrez et al. (2023). PLoS One. doi:10.1371/journal.pone.0280131",
        "Graziano et al. (2016). Clin Psychol Rev. PMID 27180913",
    ]
    com = sl.render(db, sha, "comment")
    assert com == ["Quellen: Soler-Gutiérrez 2023 (PMID 36608036); Graziano 2016 (PMID 27180913)"]
