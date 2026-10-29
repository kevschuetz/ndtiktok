"""Fake word-timestamp transcriber for tests/recording (no model download)."""

from ndc.scan.transcribe import Segment, Word, WordTranscript


class FakeTranscriber:
    """Word timestamps from plain sentences: 0.3 s per word, 0.5 s pause between sentences."""

    def __init__(self, sentences, probs=None):
        self.sentences = list(sentences)
        self.probs = probs or {}
        self.calls = []

    def transcribe_words(self, audio, language="de"):
        self.calls.append((str(audio), language))
        t, segs = 0.0, []
        for s in self.sentences:
            words = []
            for w in s.split():
                words.append(Word(t, t + 0.3, w, self.probs.get(w, 0.95)))
                t += 0.3
            segs.append(Segment(words[0].start, words[-1].end, s, words))
            t += 0.5
        return WordTranscript(segs, language, t)
