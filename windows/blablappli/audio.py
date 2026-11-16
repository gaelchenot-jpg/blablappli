"""Capture du micro et découpage aux pauses."""

from __future__ import annotations

import collections
import logging
import queue
import threading

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
BLOCK = 480  # 30 ms


class Recorder:
    """Enregistre le micro.

    - `level` (0..1) donne le volume actuel, pour animer le cercle ;
    - en mode continu, chaque morceau de parole suivi d'une pause est envoyé
      dans `on_segment` ;
    - `stop()` renvoie l'audio restant.
    """

    def __init__(self, mic_index=None, silence_seconds: float = 0.8, continuous: bool = False, on_segment=None):
        self.mic_index = mic_index
        self.silence_seconds = silence_seconds
        self.continuous = continuous
        self.on_segment = on_segment
        self.level = 0.0
        self._q: queue.Queue[np.ndarray] = queue.Queue()
        self._stream = None
        self._thread = None
        self._running = False
        self._buffer: list[np.ndarray] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        import sounddevice as sd

        self._running = True
        self._buffer = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=BLOCK,
            device=self.mic_index,
            callback=self._callback,
        )
        self._stream.start()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _callback(self, indata, frames, time_info, status):
        self._q.put(indata[:, 0].copy())

    def _loop(self) -> None:
        noise = 0.004                      # niveau de bruit de fond estimé
        silent_blocks = 0
        speech_blocks = 0
        pre_roll = collections.deque(maxlen=10)  # 300 ms avant le début de la parole
        in_speech = False
        blocks_for_pause = int(self.silence_seconds * SAMPLE_RATE / BLOCK)
        while self._running or not self._q.empty():
            try:
                block = self._q.get(timeout=0.1)
            except queue.Empty:
                continue
            rms = float(np.sqrt(np.mean(block * block)) + 1e-9)
            self.level = min(1.0, rms * 12)
            is_speech = rms > max(noise * 3.0, 0.008)
            if not is_speech:
                noise = 0.95 * noise + 0.05 * rms

            if not self.continuous:
                with self._lock:
                    self._buffer.append(block)
                continue

            # Mode continu : on découpe à chaque pause
            if is_speech:
                if not in_speech:
                    in_speech = True
                    with self._lock:
                        self._buffer = list(pre_roll)
                speech_blocks += 1
                silent_blocks = 0
                with self._lock:
                    self._buffer.append(block)
            elif in_speech:
                silent_blocks += 1
                with self._lock:
                    self._buffer.append(block)
                if silent_blocks >= blocks_for_pause:
                    if speech_blocks >= 8:  # au moins ~250 ms de parole
                        self._emit()
                    else:
                        with self._lock:
                            self._buffer = []
                    in_speech = False
                    speech_blocks = silent_blocks = 0
            else:
                pre_roll.append(block)
            # sécurité : on coupe un morceau trop long (25 s)
            if in_speech and len(self._buffer) * BLOCK > 25 * SAMPLE_RATE:
                self._emit()
                speech_blocks = 0
        self.level = 0.0

    def _emit(self) -> None:
        with self._lock:
            audio = np.concatenate(self._buffer) if self._buffer else None
            self._buffer = []
        if audio is not None and self.on_segment:
            self.on_segment(audio)

    def stop(self) -> np.ndarray | None:
        self._running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                log.exception("arrêt du micro")
            self._stream = None
        if self._thread is not None:
            self._thread.join(timeout=2)
        with self._lock:
            audio = np.concatenate(self._buffer) if self._buffer else None
            self._buffer = []
        if audio is None or len(audio) < SAMPLE_RATE * 0.3:
            return None
        return audio


def list_microphones() -> list[tuple[int, str]]:
    try:
        import sounddevice as sd

        out = []
        for i, d in enumerate(sd.query_devices()):
            # hostapi 0 = MME sous Windows : chaque micro n'apparaît qu'une fois
            if d["max_input_channels"] > 0 and d["hostapi"] == 0:
                out.append((i, d["name"]))
        return out
    except Exception:
        return []
