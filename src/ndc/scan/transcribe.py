"""faster-whisper transcription for spoken citations (D-17). CPU, int8, one thread.

The model is loaded lazily on first use, so importing this module needs neither the package
weights nor the analyze extra. Weights download once into model_dir (/data/models) from the
official Systran repo on Hugging Face.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Transcript:
    text: str
    language: str | None
    duration_s: float | None


class Transcriber:
    def __init__(
        self,
        model: str = "small",
        compute_type: str = "int8",
        cpu_threads: int = 1,
        model_dir: str | Path = "/data/models",
    ):
        self.model_name = model
        self.compute_type = compute_type
        self.cpu_threads = int(cpu_threads)
        self.model_dir = str(model_dir)
        self._model = None

    @classmethod
    def from_config(cls, analysis: dict) -> "Transcriber":
        return cls(
            model=analysis.get("whisper_model", "small"),
            compute_type=analysis.get("whisper_compute_type", "int8"),
            cpu_threads=analysis.get("whisper_cpu_threads", 1),
            model_dir=analysis.get("model_dir", "/data/models"),
        )

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # analyze extra; imported lazily

            self._model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
                num_workers=1,
                download_root=self.model_dir,
            )
        return self._model

    def transcribe(self, audio) -> Transcript:
        """audio: 16 kHz mono float32 numpy array (preferred) or a file path.

        Pass the array from pitch.decode_audio: faster-whisper 1.2.1's own file decoder calls
        av.open(metadata_errors=...), which PyAV >= 15 removed."""
        if isinstance(audio, (str, Path)):
            from ndc.scan.pitch import decode_audio

            audio = decode_audio(audio)
        segments, info = self._load().transcribe(audio, language=None, vad_filter=True)
        text = " ".join(s.text.strip() for s in segments).strip()
        return Transcript(text=text, language=info.language, duration_s=info.duration)


@dataclass
class Word:
    start: float
    end: float
    word: str
    prob: float


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word]


@dataclass
class WordTranscript:
    segments: list[Segment]
    language: str | None
    duration_s: float | None

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments).strip()

    @property
    def words(self) -> list[Word]:
        return [w for s in self.segments for w in s.words]


def transcribe_words(self: Transcriber, audio, language: str | None = "de") -> WordTranscript:
    """Word-timestamped transcription for the recording diff (plan 03-03). Same decoding path as
    transcribe(); `language` fixed to the script language so Whisper never guesses."""
    if isinstance(audio, (str, Path)):
        from ndc.scan.pitch import decode_audio

        audio = decode_audio(audio)
    segments, info = self._load().transcribe(
        audio, language=language, vad_filter=True, word_timestamps=True
    )
    out = []
    for s in segments:
        words = [
            Word(w.start, w.end, w.word.strip(), float(w.probability)) for w in (s.words or [])
        ]
        out.append(Segment(s.start, s.end, s.text.strip(), words))
    return WordTranscript(out, info.language, info.duration)


Transcriber.transcribe_words = transcribe_words  # type: ignore[attr-defined]
