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
| Android | 🧪 première version (dossier `android/`) |

## Installer sur Windows

1. Télécharge **blablappli-installation.exe** : https://github.com/gaelchenot-jpg/blablappli/releases/download/windows-latest/blablappli-installation.exe
2. Double-clique dessus.
   - Si Windows affiche « Windows a protégé votre ordinateur », clique sur **Informations complémentaires** puis **Exécuter quand même** (l'appli n'est pas signée, c'est normal pour une appli perso).
3. Suis les étapes (tu peux cocher « Lancer blablappli au démarrage de Windows »). Pas besoin de droits administrateur.
4. Au premier lancement, blablappli télécharge le modèle de reconnaissance vocale (environ 500 Mo, une seule fois) : le cercle reste gris quelques minutes, puis devient bleu. Ensuite tout marche sans internet.

Pour désinstaller : *Paramètres Windows* → *Applications* → blablappli → *Désinstaller*.

<details><summary>Ancienne méthode (script)</summary>

Télécharge le dépôt (bouton vert **Code** → **Download ZIP**), décompresse-le, puis double-clique sur `windows\installer.bat`.
</details>

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

## Installer sur Android

1. Sur ton téléphone, télécharge **blablappli.apk** : https://github.com/gaelchenot-jpg/blablappli/releases/download/android-latest/blablappli.apk
2. **Si Play Protect affiche « Appli bloquée pour protéger votre appareil »** (avec seulement un bouton OK) : c'est normal. Google bloque automatiquement toute appli installée hors du Play Store qui utilise l'*Accessibilité*, et c'est justement ce qui permet au cercle d'écrire dans les autres applis. Aucune signature ou réglage dans l'appli ne peut éviter ce blocage. Pour installer quand même :
   - ouvre le **Play Store** → touche ta **photo de profil** en haut à droite → **Play Protect** → la **roue dentée** en haut à droite ;
   - désactive **« Rechercher les menaces sur les applis avec Play Protect »** ;
   - rouvre **blablappli.apk** et installe-le ;
   - reviens dans Play Protect et **réactive** l'option. blablappli reste installé.
3. Ouvre le fichier. Android demande d'autoriser l'installation depuis ton navigateur : accepte.
4. Ouvre blablappli et suis les 2 étapes : **autoriser le micro**, puis **activer le cercle** dans les réglages d'Accessibilité.
   - Si l'interrupteur est grisé (« paramètre restreint ») : *Infos de l'appli* → ⋮ en haut à droite → *Autoriser les paramètres restreints*, puis recommence.
5. Le cercle apparaît sur le côté de l'écran, par-dessus toutes les applis.

**Utilisation** : touche un champ de texte, touche le cercle, parle, touche-le encore. Appui long sur le cercle : synonymes, répétitions, dictée continue.

Sur Android, la reconnaissance vocale (Vosk) n'ajoute pas la ponctuation toute seule : dis « virgule », « point », « point d'interrogation », « à la ligne »… Les majuscules en début de phrase sont automatiques. Les mots reconnus sont toujours bien orthographiés ; la correction de grammaire (accords) n'est pas encore disponible sur Android.

## Outils libres utilisés

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (reconnaissance vocale, modèle Whisper d'OpenAI, licence MIT)
- [Grammalecte](https://grammalecte.net) (correcteur français, GPL)
- Thésaurus français de [LibreOffice](https://github.com/LibreOffice/dictionaries) (LGPL)
- [Vosk](https://alphacephei.com/vosk/) (reconnaissance vocale hors ligne sur Android, Apache 2.0)
- [PySide6 / Qt](https://www.qt.io/qt-for-python) (interface, LGPL)
