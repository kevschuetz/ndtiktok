from ndc.sources.split import split_sentences


def test_german_abbreviations_do_not_split():
    text = (
        "Bei Erwachsenen soll z. B. Psychoedukation angeboten werden. "
        "Die Evidenz ist hoch (vgl. Abb. 3). Ca. 5 % sind betroffen."
    )
    assert split_sentences(text, "de") == [
        "Bei Erwachsenen soll z. B. Psychoedukation angeboten werden.",
        "Die Evidenz ist hoch (vgl. Abb. 3).",
        "Ca. 5 % sind betroffen.",
    ]


def test_english_abbreviations_do_not_split():
    text = "Smith et al. reported e.g. lower scores in adults. A second sentence follows here."
    assert split_sentences(text, "en") == [
        "Smith et al. reported e.g. lower scores in adults.",
        "A second sentence follows here.",
    ]


def test_short_fragments_dropped_and_whitespace_normalized():
    assert split_sentences("Results.  Adults   with ADHD differ clearly.\n", "en") == [
        "Adults with ADHD differ clearly."
    ]


def test_unknown_lang_rejected():
    import pytest

    with pytest.raises(ValueError):
        split_sentences("x y z", "fr")
