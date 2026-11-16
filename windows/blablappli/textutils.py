"""Traitements de texte : commandes vocales, raccords entre phrases, répétitions."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

# Phrases que Whisper "invente" parfois pendant un silence (vu dans les sous-titres)
HALLUCINATIONS = [
    "sous-titres réalisés par la communauté d'amara.org",
    "sous-titrage st'501",
    "sous-titrage société radio-canada",
    "merci d'avoir regardé cette vidéo",
    "merci d'avoir regardé",
    "abonnez-vous",
    "sous-titres fait par",
    "sous-titrage fr",
    "...",
]


def is_hallucination(text: str) -> bool:
    t = text.strip().lower().replace("’", "'")
    if not t:
        return True
    t2 = re.sub(r"[\s.!?,]+$", "", t)
    return any(t2 == h or t2.startswith(h) for h in HALLUCINATIONS) or not re.search(r"\w", t)


# --- Commandes vocales -------------------------------------------------------

_COMMANDS = [
    (r"\s*\bnouveau paragraphe\b[,.]?\s*", "\n\n"),
    (r"[,.]?\s*\bpoint,? à la ligne\b[,.]?\s*", ".\n"),
    (r"\s*\b(?:retour )?à la ligne\b[,.]?\s*", "\n"),
    (r"\s*\bouvrez? les guillemets\b[,.]?\s*", " « "),
    (r"[,.]?\s*\bfermez? les guillemets\b", " »"),
    (r"\s*\bpoint d'interrogation\b[,.]?", " ?"),
    (r"\s*\bpoint d'exclamation\b[,.]?", " !"),
    (r"\s*\bdeux points\b[,.]?", " :"),
    (r"\s*\bpoint virgule\b[,.]?", " ;"),
]


def apply_voice_commands(text: str) -> str:
    out = text
    for pattern, repl in _COMMANDS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    # Majuscule après un retour à la ligne
    out = re.sub(r"(\n+)\s*([a-zàâäéèêëîïôöùûüç])", lambda m: m.group(1) + m.group(2).upper(), out)
    return out.strip(" ")


def join_segment(previous: str, segment: str) -> str:
    """Prépare un nouveau morceau dicté pour qu'il s'enchaîne avec le précédent.

    Ajoute une espace devant, et met une minuscule si la phrase précédente
    n'était pas terminée.
    """
    seg = segment.strip()
    if not seg:
        return ""
    if not previous:
        return seg
    prev = previous.rstrip(" ")
    if prev.endswith("\n"):
        return seg
    ended = prev[-1:] in ".!?…»"
    if not ended and seg[:1].isupper() and not _looks_like_proper_noun(seg):
        seg = seg[0].lower() + seg[1:]
    return " " + seg


def _looks_like_proper_noun(seg: str) -> bool:
    first = re.match(r"\w+", seg)
    if not first:
        return False
    w = first.group(0)
    return w.isupper() and len(w) > 1  # sigle (ex. "SNCF")


# --- Répétitions --------------------------------------------------------------

STOPWORDS = set(
    """
    a à ai aie aient aies ait alors as au aucun aura aurai auraient aurais aurait auras aurez auriez
    aurions aurons auront aussi autre aux avaient avais avait avant avec avez aviez avions avoir avons
    ayant ayez ayons bon c ça car ce ceci cela celle celles celui cependant certes ces cet cette ceux
    chaque chez ci comme comment d dans de des deux devrait doit donc dont du elle elles en encore
    entre es est et étaient étais était étant été êtes étiez étions être eu eue eues eurent eus eusse
    eut eux fait faire fais faut fois font furent fut il ils j je jusqu l la le les leur leurs lui m
    ma mais me même mêmes mes moi mon n ne ni non nos notre nous on ont ou où par parce pas peu peut
    plus pour pourquoi qu quand que quel quelle quelles quels qui quoi s sa sans se sera serai seraient
    serais serait seras serez seriez serions serons seront ses si sien son sont sous soyez soyons suis
    sur t ta te tes toi ton tous tout toute toutes très tu un une vers voici voilà vos votre vous y
    oui ici là cet après ainsi alors bien beaucoup faisait avait sont tout tous rien
    """.split()
)

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]+(?:-[A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]+)*")


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def word_key(word: str) -> str:
    """Clé approximative pour regrouper les formes d'un même mot (pluriel, féminin)."""
    w = _strip_accents(word.lower())
    for suffix in ("es", "s", "x", "e"):
        if len(w) > 4 and w.endswith(suffix):
            w = w[: -len(suffix)]
            break
    return w


@dataclass
class Repetition:
    key: str
    words: list[str]               # formes rencontrées
    spans: list[tuple[int, int]]   # positions (début, fin) dans le texte

    @property
    def count(self) -> int:
        return len(self.spans)

    @property
    def label(self) -> str:
        return self.words[0].lower()


def find_repetitions(text: str, window: int = 40, min_len: int = 4) -> list[Repetition]:
    """Repère les mots répétés à moins de `window` mots d'écart.

    Les petits mots (le, de, est…) sont ignorés.
    """
    tokens = []
    for m in WORD_RE.finditer(text):
        w = m.group(0)
        if len(w) < min_len or w.lower() in STOPWORDS:
            tokens.append(None)
            continue
        tokens.append((word_key(w), w, m.start(), m.end()))

    positions: dict[str, list[int]] = defaultdict(list)
    for i, t in enumerate(tokens):
        if t:
            positions[t[0]].append(i)

    result = []
    for key, idxs in positions.items():
        if len(idxs) < 2:
            continue
        keep = set()
        for a, b in zip(idxs, idxs[1:]):
            if b - a <= window:
                keep.update((a, b))
        if not keep:
            continue
        ordered = sorted(keep)
        words, spans = [], []
        for i in ordered:
            _, w, s, e = tokens[i]
            spans.append((s, e))
            if w.lower() not in (x.lower() for x in words):
                words.append(w)
        result.append(Repetition(key, words, spans))
    result.sort(key=lambda r: (-r.count, r.spans[0][0]))
    return result


def match_case(original: str, replacement: str) -> str:
    """Applique au remplaçant la casse du mot d'origine."""
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement
