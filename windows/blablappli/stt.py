"""Reconnaissance vocale hors ligne avec faster-whisper."""

from __future__ import annotations

import logging

import numpy as np

from .config import app_dir
from .textutils import is_hallucination

log = logging.getLogger(__name__)


class SpeechToText:
    def __init__(self, model: str = "small", device: str = "auto"):
        from faster_whisper import WhisperModel

        root = app_dir() / "modeles"
        self.model_name = model
        self.model = None
        tries = []
        if device in ("auto", "cuda"):
            tries.append(("cuda", "float16"))
        if device in ("auto", "cpu"):
            tries.append(("cpu", "int8"))
        last_err = None
        for dev, ctype in tries:
            try:
                self.model = WhisperModel(model, device=dev, compute_type=ctype, download_root=str(root))
                self.device = dev
                log.info("Modèle %s chargé sur %s", model, dev)
                break
            except Exception as e:  # pas de carte graphique compatible, etc.
                last_err = e
                log.info("Impossible de charger sur %s : %s", dev, e)
        if self.model is None:
            raise RuntimeError(f"Impossible de charger le modèle Whisper : {last_err}")

    def transcribe(self, audio: np.ndarray, context: str = "") -> str:
        segments, _info = self.model.transcribe(
            audio,
            language="fr",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,
            initial_prompt=(context[-200:] if context else None),
            no_speech_threshold=0.6,
        )
        parts = []
        for s in segments:
            if s.no_speech_prob > 0.8 or is_hallucination(s.text):
                continue
            parts.append(s.text.strip())
        return " ".join(parts).strip()
