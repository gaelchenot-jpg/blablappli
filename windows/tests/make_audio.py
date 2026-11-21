"""Fabrique les phrases de l'essai complet avec une voix française (Piper).

    python make_audio.py voix.onnx dossier_sortie
"""
import sys
import wave
from pathlib import Path

from piper import PiperVoice

voice = PiperVoice.load(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
lines = (Path(__file__).parent / "audio" / "phrases.txt").read_text(encoding="utf-8").splitlines()
for i, line in enumerate(l for l in lines if l.strip()):
    said, expected = line.split("|")
    path = out / f"{i + 1:02d}.wav"
    with wave.open(str(path), "wb") as w:
        if hasattr(voice, "synthesize_wav"):
            voice.synthesize_wav(said, w)
        else:
            voice.synthesize(said, w)
    (out / f"{i + 1:02d}.txt").write_text(expected, encoding="utf-8")
    print(path, path.stat().st_size)
