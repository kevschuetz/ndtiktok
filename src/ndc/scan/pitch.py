"""Voice gender as a pitch estimate (D-17), always labelled method `pitch_estimate`.

Frame-wise autocorrelation F0 (70-400 Hz) on voiced frames, median over frames. The median is
classified with config thresholds (male <= male_max_hz, female >= female_min_hz, the band in
between is `unknown`). This is a heuristic: it is an estimate, never a fact, and conflicts with
the visible speaker or ambiguous values go to the operator.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

METHOD = "pitch_estimate"
SR = 16000
F0_MIN, F0_MAX = 70.0, 400.0
FRAME_S, HOP_S = 0.04, 0.02
RMS_MIN = 0.01  # below this a frame counts as silence
CORR_MIN = 0.6  # normalized autocorrelation peak for a voiced frame


@dataclass
class PitchEstimate:
    median_hz: float | None
    gender: str  # male | female | unknown
    confidence: str  # low | medium | high
    voiced_share: float
    method: str = METHOD
    f0: list = field(default_factory=list, repr=False)


def _frame_f0(frame: np.ndarray, sr: int) -> float | None:
    frame = frame - frame.mean()
    if np.sqrt(np.mean(frame**2)) < RMS_MIN:
        return None
    n = len(frame)
    spec = np.fft.rfft(frame, 2 * n)
    ac = np.fft.irfft(spec * np.conj(spec))[:n]
    if ac[0] <= 0:
        return None
    ac = ac / ac[0]
    lo, hi = int(sr / F0_MAX), min(int(sr / F0_MIN), n - 2)
    seg = ac[lo : hi + 1]
    peak = float(seg.max())
    if peak < CORR_MIN:
        return None
    # earliest local maximum within 90% of the best peak: avoids sub-harmonic (octave-down) picks
    lag = None
    for i in range(1, len(seg) - 1):
        if seg[i] >= 0.9 * peak and seg[i] >= seg[i - 1] and seg[i] >= seg[i + 1]:
            lag = i + lo
            break
    if lag is None:
        lag = int(seg.argmax()) + lo
    y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
    denom = y0 - 2 * y1 + y2
    shift = 0.5 * (y0 - y2) / denom if denom != 0 else 0.0
    return sr / (lag + shift)


def f0_track(samples: np.ndarray, sr: int = SR) -> tuple[list[float], int]:
    """(voiced F0 values, number of frames)."""
    samples = np.asarray(samples, dtype=np.float64)
    flen, hop = int(FRAME_S * sr), int(HOP_S * sr)
    out, frames = [], 0
    for start in range(0, max(len(samples) - flen + 1, 0), hop):
        frames += 1
        f0 = _frame_f0(samples[start : start + flen], sr)
        if f0 is not None and F0_MIN <= f0 <= F0_MAX:
            out.append(f0)
    return out, frames


def classify(
    f0: list[float], frames: int, male_max_hz: float = 160, female_min_hz: float = 185
) -> PitchEstimate:
    share = len(f0) / frames if frames else 0.0
    if len(f0) < 10:
        return PitchEstimate(None, "unknown", "low", share, f0=list(f0))
    med = float(np.median(f0))
    q1, q3 = np.percentile(f0, [25, 75])
    spread = float((q3 - q1) / med) if med else 1.0
    if med <= male_max_hz:
        gender = "male"
    elif med >= female_min_hz:
        gender = "female"
    else:
        gender = "unknown"
    if gender == "unknown":
        conf = "low"
    elif share >= 0.3 and spread < 0.15:
        conf = "high"
    elif share >= 0.1:
        conf = "medium"
    else:
        conf = "low"
    return PitchEstimate(round(med, 1), gender, conf, round(share, 3), f0=list(f0))


def estimate_from_samples(
    samples: np.ndarray, sr: int = SR, male_max_hz: float = 160, female_min_hz: float = 185
) -> PitchEstimate:
    f0, frames = f0_track(samples, sr)
    return classify(f0, frames, male_max_hz, female_min_hz)


def combine(
    estimates: list[PitchEstimate], male_max_hz: float = 160, female_min_hz: float = 185
) -> PitchEstimate:
    """Pool the voiced F0 values of several videos into one account-level estimate."""
    pooled = [x for e in estimates for x in e.f0]
    frames = sum(int(len(e.f0) / e.voiced_share) if e.voiced_share else 0 for e in estimates)
    return classify(pooled, max(frames, len(pooled)), male_max_hz, female_min_hz)


def decode_audio(path: str | Path, sr: int = SR, max_seconds: float | None = None) -> np.ndarray:
    """Decode a media file to mono float32 at `sr` with PyAV (analyze extra)."""
    import av  # analyze extra; imported lazily

    chunks = []
    total = 0
    limit = int(max_seconds * sr) if max_seconds else None
    with av.open(str(path)) as container:
        if not container.streams.audio:
            return np.zeros(0, dtype=np.float32)
        resampler = av.AudioResampler(format="flt", layout="mono", rate=sr)
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                arr = out.to_ndarray().reshape(-1)
                chunks.append(arr)
                total += len(arr)
            if limit and total >= limit:
                break
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    data = np.concatenate(chunks).astype(np.float32)
    return data[:limit] if limit else data


def estimate_from_file(
    path: str | Path, male_max_hz: float = 160, female_min_hz: float = 185, max_seconds=180
) -> PitchEstimate:
    return estimate_from_samples(
        decode_audio(path, SR, max_seconds), SR, male_max_hz, female_min_hz
    )
