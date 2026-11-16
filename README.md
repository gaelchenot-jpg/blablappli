# blablappli

Dictée vocale en français, gratuite et hors ligne, qui écrit dans **n'importe quel logiciel** (Word, navigateur, mails…).

- 🎙️ Un **cercle flottant** façon « Jarvis » : un clic pour démarrer, un clic pour arrêter.
- ♾️ Option **dictée continue** : le texte s'écrit au fur et à mesure, à chaque pause.
- ✍️ **Correction automatique** de l'orthographe et de la grammaire (Grammalecte).
- 🔁 Repère les **répétitions** et propose des **synonymes** sur demande.
- 🔒 Tout fonctionne **sur ton ordinateur**, sans internet (une fois installé).

| Version | État |
|---|---|
| Windows | ✅ première version (dossier `windows/`) |
| Android | 🔜 à venir |

## Installer sur Windows

1. Télécharge le dossier (bouton vert **Code** → **Download ZIP** sur GitHub) et décompresse-le, par exemple dans `Documents`.
2. Ouvre le dossier `windows` et double-clique sur **`installer.bat`**.
   - Si Windows affiche « Windows a protégé votre ordinateur », clique sur **Informations complémentaires** puis **Exécuter quand même**.
   - L'installation télécharge Python (si besoin), les composants, le correcteur, le dictionnaire des synonymes et le modèle de reconnaissance vocale (environ 1 Go en tout). Compte 5 à 15 minutes.
3. À la fin, blablappli se lance et une icône **blablappli** apparaît sur le Bureau.

## Utiliser blablappli

- **Clic** sur le cercle : démarre la dictée (le cercle s'illumine). **Re-clic** : arrête, le texte s'écrit là où se trouve ton curseur.
- **Glisser** le cercle pour le déplacer.
- **Clic droit** sur le cercle : le menu.
  - *Dictée continue* : le texte s'écrit à chaque pause, sans attendre le second clic.
  - *Synonymes du mot sélectionné* : sélectionne un mot dans ton texte, puis choisis un synonyme, il remplace le mot.
  - *Répétitions du texte sélectionné* : ouvre une fenêtre où les mots répétés sont surlignés. Clique sur un mot, puis sur un synonyme, puis **Remettre dans le document**.
  - *Précision de la reconnaissance* : « Équilibré » par défaut. « Précis » est meilleur mais plus lent.
  - *Lancer au démarrage de Windows*.
- Une **pastille orange** avec un chiffre sur le cercle indique le nombre de mots répétés dans ta dernière dictée.

### Raccourcis clavier

| Raccourci | Action |
|---|---|
| `Ctrl + Alt + D` | Démarrer / arrêter la dictée |
| `Ctrl + Alt + S` | Synonymes du mot sélectionné |
| `Ctrl + Alt + R` | Répétitions du texte sélectionné |

### Commandes vocales

| Tu dis | Ça donne |
|---|---|
| « à la ligne » | retour à la ligne |
| « point à la ligne » | `.` puis retour à la ligne |
| « nouveau paragraphe » | ligne vide |
| « ouvrez les guillemets » / « fermez les guillemets » | « … » |

La ponctuation (virgules, points, points d'interrogation) est ajoutée automatiquement d'après ton intonation.

## En cas de problème

- Lance **`lancer-avec-messages.bat`** (dans `windows/`) : une fenêtre affiche ce qui se passe.
- Le journal se trouve dans `%APPDATA%\blablappli\blablappli.log`.
- Les réglages sont dans `%APPDATA%\blablappli\config.json`.

## Outils libres utilisés

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (reconnaissance vocale, modèle Whisper d'OpenAI, licence MIT)
- [Grammalecte](https://grammalecte.net) (correcteur français, GPL)
- Thésaurus français de [LibreOffice](https://github.com/LibreOffice/dictionaries) (LGPL)
- [PySide6 / Qt](https://www.qt.io/qt-for-python) (interface, LGPL)
