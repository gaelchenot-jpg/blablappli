from pathlib import Path

from blablappli.corrector import Corrector, _apply_edits
from blablappli.textutils import (
    apply_voice_commands,
    find_repetitions,
    is_hallucination,
    join_segment,
    match_case,
)
from blablappli.thesaurus import Thesaurus

THES = """UTF-8
maison|2
(nom)|demeure|habitation|logis|foyer
(nom)|famille|lignée
rapide|1
(adj)|prompt|vif|véloce (soutenu)
"""


def test_repetitions():
    text = "Le chat est très beau. Le chat dort sur le canapé, et les chats aiment dormir."
    reps = {r.key: r for r in find_repetitions(text)}
    assert "chat" in reps and reps["chat"].count == 3
    assert "le" not in reps  # petits mots ignorés


def test_repetitions_window():
    far = "maison " + " ".join(["mot%d" % i for i in range(60)]) + " maison"
    assert find_repetitions(far, window=40) == []
    assert find_repetitions(far, window=80)


def test_voice_commands():
    assert apply_voice_commands("Bonjour Pierre, à la ligne merci pour ton message") == "Bonjour Pierre,\nMerci pour ton message"
    assert apply_voice_commands("Fin du texte point à la ligne Suite") == "Fin du texte.\nSuite"
    assert apply_voice_commands("Un. Nouveau paragraphe. Deux.") == "Un.\n\nDeux."


def test_join():
    assert join_segment("", "Bonjour.") == "Bonjour."
    assert join_segment("Je pense que", "Tu as raison.") == " tu as raison."
    assert join_segment("C'est fini.", "Demain on part.") == " Demain on part."
    assert join_segment("Je prends le", "TGV ce soir.") == " TGV ce soir."


def test_hallucination():
    assert is_hallucination("Sous-titres réalisés par la communauté d'Amara.org")
    assert is_hallucination("  ...  ")
    assert not is_hallucination("Bonjour à tous.")


def test_match_case():
    assert match_case("Maison", "demeure") == "Demeure"
    assert match_case("maison", "demeure") == "demeure"


def test_thesaurus(tmp_path: Path):
    p = tmp_path / "thes_fr.dat"
    p.write_text(THES, encoding="utf-8")
    t = Thesaurus(p)
    assert t.synonyms("maison")[:2] == ["demeure", "habitation"]
    assert t.synonyms("Maisons")[0] == "Demeure"  # pluriel + majuscule
    assert "véloce" in t.synonyms("rapides")


def test_apply_edits():
    assert _apply_edits("il sont venu", [(3, 7, "sont"), (8, 12, "venus")]) == "il sont venus"
    assert _apply_edits("abc def", [(0, 3, "X"), (1, 5, "Y")]) in ("X def", "aYef")


def test_corrector_runs():
    c = Corrector()
    out = c.correct("Bonjour, je suis aller a la maisson.")
    print(c.engine, "->", out)
    if c.engine == "pyspellchecker":
        assert "maison" in out
