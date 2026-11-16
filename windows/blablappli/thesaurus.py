"""Synonymes à partir du thésaurus libre de LibreOffice (format MyThes, thes_fr.dat)."""

from __future__ import annotations

import threading
from pathlib import Path

from .config import DATA_DIR
from .textutils import match_case


class Thesaurus:
    def __init__(self, path: Path | None = None):
        self.path = path or DATA_DIR / "thes_fr.dat"
        self._index: dict[str, list[tuple[str, list[str]]]] | None = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.path.exists()

    def _load(self) -> None:
        index: dict[str, list[tuple[str, list[str]]]] = {}
        with open(self.path, "rb") as f:
            raw = f.read()
        first_nl = raw.find(b"\n")
        encoding = raw[:first_nl].decode("ascii", "ignore").strip() or "utf-8"
        if encoding.upper() in ("ISO8859-1", "ISO-8859-1"):
            encoding = "latin-1"
        lines = raw[first_nl + 1 :].decode(encoding, "replace").splitlines()
        i = 0
        while i < len(lines):
            head = lines[i]
            i += 1
            if "|" not in head:
                continue
            word, _, n = head.rpartition("|")
            try:
                n = int(n)
            except ValueError:
                continue
            meanings = []
            for line in lines[i : i + n]:
                parts = line.split("|")
                pos = parts[0].strip("() ")
                syns = [_clean(p) for p in parts[1:] if p.strip()]
                if syns:
                    meanings.append((pos, syns))
            i += n
            key = word.lower()
            index.setdefault(key, []).extend(meanings)
        self._index = index

    def lookup(self, word: str) -> list[tuple[str, list[str]]]:
        """Renvoie les sens du mot : [(nature, [synonymes...]), ...]."""
        if not self.available:
            return []
        with self._lock:
            if self._index is None:
                self._load()
        w = word.strip().lower()
        candidates = [w]
        # formes de base approximatives : pluriel, féminin
        for suf, rep in (("s", ""), ("x", ""), ("es", ""), ("e", ""), ("aux", "al"), ("euses", "eux"), ("euse", "eux")):
            if w.endswith(suf) and len(w) > len(suf) + 2:
                candidates.append(w[: -len(suf)] + rep)
        for c in candidates:
            if c in self._index:
                return self._index[c]
        return []

    def synonyms(self, word: str, limit: int = 24) -> list[str]:
        """Liste à plat des synonymes, sans doublon, avec la casse du mot d'origine."""
        seen, out = set(), []
        for _, syns in self.lookup(word):
            for s in syns:
                if s.lower() == word.lower() or s.lower() in seen:
                    continue
                seen.add(s.lower())
                out.append(match_case(word, s))
                if len(out) >= limit:
                    return out
        return out


def _clean(s: str) -> str:
    s = s.strip()
    # retire les précisions entre parenthèses, ex. "maison (générique)"
    if "(" in s:
        s = s.split("(")[0].strip()
    return s
