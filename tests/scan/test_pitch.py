"""Pitch-based voice estimate (plan 01-06 Task 3, D-17): labelled pitch_estimate."""

import numpy as np
import pytest

from ndc.scan import pitch

SR = 16000


def _tone(hz, seconds=2.0, harmonics=True):
    t = np.arange(int(SR * seconds)) / SR
    y = np.sin(2 * np.pi * hz * t)
    if harmonics:  # voice-like: a few harmonics
        y = y + 0.5 * np.sin(2 * np.pi * 2 * hz * t) + 0.25 * np.sin(2 * np.pi * 3 * hz * t)
    return (0.3 * y / np.max(np.abs(y))).astype(np.float32)


def test_male_tone():
    est = pitch.estimate_from_samples(_tone(120), SR)
    assert est.median_hz == pytest.approx(120, rel=0.05)
    assert est.gender == "male" and est.method == "pitch_estimate"
    assert est.confidence in ("medium", "high")


def test_female_tone():
    est = pitch.estimate_from_samples(_tone(220), SR)
    assert est.median_hz == pytest.approx(220, rel=0.05)
    assert est.gender == "female"


def test_ambiguous_band():
    est = pitch.estimate_from_samples(_tone(170), SR)
    assert est.gender == "unknown"


def test_silence():
    est = pitch.estimate_from_samples(np.zeros(SR * 2, dtype=np.float32), SR)
    assert est.gender == "unknown" and est.confidence == "low" and est.median_hz is None


def test_thresholds_from_config():
    est = pitch.estimate_from_samples(_tone(170), SR, male_max_hz=180, female_min_hz=200)
    assert est.gender == "male"


def test_combine_videos():
    a = pitch.estimate_from_samples(_tone(118), SR)
    b = pitch.estimate_from_samples(_tone(125), SR)
    c = pitch.estimate_from_samples(np.zeros(SR, dtype=np.float32), SR)
    comb = pitch.combine([a, b, c])
    assert comb.gender == "male" and comb.method == "pitch_estimate"
