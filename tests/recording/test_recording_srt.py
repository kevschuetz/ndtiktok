from ndc.recording import srt


def test_timestamp_format():
    assert srt._ts(0) == "00:00:00,000"
    assert srt._ts(61.234) == "00:01:01,234"
    assert srt._ts(3661.5) == "01:01:01,500"


def test_wrap_two_lines_at_word_boundary():
    text = "Erwachsene mit ADHS greifen häufiger zu wenig hilfreichen Strategien im Alltag."
    w = srt._wrap(text)
    lines = w.split("\n")
    assert len(lines) == 2 and all(len(line) <= srt.MAX_LINE for line in lines)
    assert " ".join(lines) == text


def test_long_sentence_split_into_cues_with_word_times():
    words = [[i * 0.3, i * 0.3 + 0.3, f"w{i}", 0.9] for i in range(30)]
    text = " ".join(f"w{i}" for i in range(30))  # 30 tokens, > 84 chars
    chunks = srt._chunks(text, words, 0.0, 9.0)
    assert len(chunks) >= 2 and all(len(t) <= srt.MAX_CUE for _, _, t in chunks)
    assert chunks[0][0] == 0.0 and chunks[-1][1] == words[-1][1]
    assert all(chunks[i][1] <= chunks[i + 1][0] + 1e-9 for i in range(len(chunks) - 1))
