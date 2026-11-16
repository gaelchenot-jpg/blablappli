"""Correction automatique de l'orthographe et de la grammaire.

Utilise Grammalecte (correcteur libre français, hors ligne). Si Grammalecte
n'est pas installé, une correction d'orthographe plus simple est utilisée
(pyspellchecker).
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

# Options de Grammalecte qu'on coupe : elles touchent à la typographie
# (espaces insécables, apostrophes courbes) et surprennent dans certains logiciels.
_DISABLED_OPTIONS = {"apos": False, "nbsp": False, "esp": False, "tab": False, "unit": False, "typo": False}


class Corrector:
    def __init__(self):
        self.engine = "aucun"
        self._gc = None
        self._spell = None
        try:
            import grammalecte  # type: ignore

            self._gc = grammalecte.GrammarChecker("fr")
            try:
                opts = self._gc.gce.getOptions()
                self._gc.gce.setOptions({k: v for k, v in _DISABLED_OPTIONS.items() if k in opts})
            except Exception:
                pass
            self.engine = "Grammalecte"
        except Exception as e:  # pas installé
            log.warning("Grammalecte indisponible (%s), correction simplifiée", e)
            try:
                from spellchecker import SpellChecker  # type: ignore

                self._spell = SpellChecker(language="fr")
                self.engine = "pyspellchecker"
            except Exception as e2:
                log.warning("Aucun correcteur disponible : %s", e2)

    def correct(self, text: str) -> str:
        if not text.strip():
            return text
        try:
            if self._gc is not None:
                # plusieurs passes : une correction peut en révéler une autre
                for _ in range(2):
                    new = self._correct_grammalecte(text)
                    if new == text:
                        break
                    text = new
                return text
            if self._spell is not None:
                return self._correct_simple(text)
        except Exception:
            log.exception("Erreur pendant la correction")
        return text

    # -- Grammalecte ---------------------------------------------------------

    def _correct_grammalecte(self, text: str) -> str:
        paragraphs = text.split("\n")
        return "\n".join(self._correct_paragraph(p) for p in paragraphs)

    def _correct_paragraph(self, par: str) -> str:
        if not par.strip():
            return par
        res = self._gc.getParagraphErrors(par, bSpellSugg=True)
        if isinstance(res, tuple):
            gram_errs, spell_errs = res
        else:  # anciennes versions
            gram_errs, spell_errs = res, []
        edits = []
        for err in gram_errs or []:
            sugg = err.get("aSuggestions") or []
            if sugg:
                edits.append((int(err["nStart"]), int(err["nEnd"]), sugg[0]))
        for err in spell_errs or []:
            start, end = int(err["nStart"]), int(err["nEnd"])
            word = par[start:end]
            if word[:1].isupper():  # nom propre probable : on ne touche pas
                continue
            sugg = err.get("aSuggestions") or []
            if sugg:
                edits.append((start, end, sugg[0]))
        return _apply_edits(par, edits)

    # -- Secours -------------------------------------------------------------

    def _correct_simple(self, text: str) -> str:
        edits = []
        for m in re.finditer(r"(?<![\w'’-])[a-zàâäéèêëîïôöùûüçœæ]+(?![\w'’-])", text):  # mots en minuscules seulement
            w = m.group(0)
            if len(w) < 3 or w in self._spell:
                continue
            fix = self._spell.correction(w)
            if fix and fix != w:
                edits.append((m.start(), m.end(), fix))
        return _apply_edits(text, edits)


def _apply_edits(text: str, edits: list[tuple[int, int, str]]) -> str:
    """Applique les remplacements de la fin vers le début, en ignorant ceux qui se chevauchent."""
    out = text
    last_start = len(text) + 1
    for start, end, repl in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        if end > last_start:
            continue
        out = out[:start] + repl + out[end:]
        last_start = start
    return out
