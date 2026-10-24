from pathlib import Path

GUIDE = Path(__file__).resolve().parent.parent / "config" / "style_guide.md"


def test_style_guide_exists_and_is_substantial():
    assert len(GUIDE.read_text(encoding="utf-8").splitlines()) >= 60


def test_style_guide_keywords():
    text = GUIDE.read_text(encoding="utf-8")
    low = text.lower()
    for kw in (
        "60–75",
        "Hook",
        "0–2 s",
        "Hedging",
        "ndc check",
        "autistische Menschen",
        "Kein Ersatz für ärztliche",
        "3",
    ):
        assert kw in text, kw
    assert "ein thema" in low or "one topic" in low
    assert "untertitel" in low or "captions" in low
    assert "blitz" in low or "flash" in low
    assert "quellen" in low or "sources" in low
