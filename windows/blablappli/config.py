"""Réglages de blablappli, enregistrés dans %APPDATA%\\blablappli\\config.json."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def app_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    d = Path(base) / "blablappli"
    d.mkdir(parents=True, exist_ok=True)
    return d


# Dossier "data" livré avec l'appli (thésaurus téléchargé à l'installation)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

MODELS = {
    "base": "Rapide (moins précis)",
    "small": "Équilibré (conseillé)",
    "medium": "Précis (plus lent)",
    "large-v3-turbo": "Très précis (PC puissant)",
}


@dataclass
class Config:
    model: str = "small"
    continuous: bool = False        # écrire au fur et à mesure, à chaque pause
    autocorrect: bool = True        # correction orthographe/grammaire automatique
    voice_commands: bool = True     # "à la ligne", "nouveau paragraphe"...
    device: str = "cpu"             # "cpu", "cuda" (carte graphique NVIDIA) ou "auto"
    mic_index: int | None = None    # micro (None = micro par défaut de Windows)
    silence_seconds: float = 0.8    # durée de silence qui marque une pause
    repetition_window: int = 40     # nombre de mots dans lequel on cherche des répétitions
    bubble_x: int | None = None
    bubble_y: int | None = None
    bubble_size: int = 76
    hotkey_dictation: str = "<ctrl>+<alt>+d"
    hotkey_synonyms: str = "<ctrl>+<alt>+s"
    hotkey_repetitions: str = "<ctrl>+<alt>+r"
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Config":
        path = app_dir() / "config.json"
        cfg = cls()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
            except Exception:
                pass
        return cfg

    def save(self) -> None:
        path = app_dir() / "config.json"
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
