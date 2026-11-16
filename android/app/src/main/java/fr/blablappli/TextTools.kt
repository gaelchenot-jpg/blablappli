package fr.blablappli

import java.text.Normalizer

/** Traitements de texte : ponctuation dictée, majuscules, répétitions. */
object TextTools {

    // --- Commandes vocales -------------------------------------------------------------
    // Vosk n'écrit pas la ponctuation : on la dicte ("virgule", "point"...).
    /** Expression sans tenir compte des majuscules, avec des limites de mots qui gèrent les accents. */
    private fun R(p: String) = Regex(p.replace("<", "(?<!\\p{L})").replace(">", "(?!\\p{L})"), RegexOption.IGNORE_CASE)

    private val COMMANDS = listOf(
        R("""\s*<nouveau paragraphe>\s*""") to "\n\n",
        R("""\s*<point à la ligne>\s*""") to ".\n",
        R("""\s*<(retour )?à la ligne>\s*""") to "\n",
        R("""\s*<points? d'interrogation>""") to " ?",
        R("""\s*<points? d'exclamation>""") to " !",
        R("""\s*<points? de suspension>""") to "…",
        R("""\s*<point virgule>""") to " ;",
        R("""\s*<deux points>""") to " :",
        R("""\s*<virgule>""") to ",",
        R("""\s*<ouvre(z|r)? les guillemets>\s*""") to " « ",
        R("""\s*<ferme(z|r)? les guillemets>""") to " »",
        R("""\s*<ouvre(z|r)? la parenthèse>\s*""") to " (",
        R("""\s*<ferme(z|r)? la parenthèse>""") to ")",
        // "point" seul n'est une ponctuation qu'en fin de phrase dictée
        R("""\s+<point>$""") to ".",
    )

    fun applyVoiceCommands(text: String): String {
        var out = text.trim()
        for ((re, rep) in COMMANDS) out = re.replace(out) { rep }
        // espace manquante après une ponctuation
        out = Regex("""([,;:!?.…»)])(?=[^\s\n,.;:!?…»)])""").replace(out) { it.groupValues[1] + " " }
        // "point" en tout début (ex. dit après une pause)
        if (out.equals("point", ignoreCase = true)) out = "."
        return out.trimStart(' ')
    }

    /**
     * Prépare un morceau dicté pour qu'il s'enchaîne avec ce qui est déjà écrit
     * avant le curseur : espace devant, majuscule en début de phrase.
     */
    fun joinWith(before: String, piece: String): String {
        var p = piece
        if (p.isEmpty()) return p
        val prev = before.trimEnd(' ')
        val startsSentence = prev.isEmpty() || prev.endsWith("\n") || prev.last() in ".!?…"
        if (startsSentence) {
            val i = p.indexOfFirst { it.isLetter() }
            if (i >= 0) p = p.substring(0, i) + p[i].uppercaseChar() + p.substring(i + 1)
        }
        // majuscule après un point ou un retour dans le morceau lui-même
        p = Regex("""([.!?…]\s+|\n+)(\p{Ll})""").replace(p) { it.groupValues[1] + it.groupValues[2].uppercase() }
        val needsSpace = before.isNotEmpty() && !before.last().isWhitespace() &&
            p.first() !in ",.;:!?…)\n" && !p.startsWith(" ")
        return if (needsSpace) " $p" else p
    }

    fun process(raw: String, before: String, voiceCommands: Boolean = true): String {
        val t = if (voiceCommands) applyVoiceCommands(raw) else raw.trim()
        return joinWith(before, t)
    }

    // --- Répétitions ---------------------------------------------------------------------
    val STOPWORDS: Set<String> = """
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
        oui ici là après ainsi bien beaucoup faisait rien
    """.trim().split(Regex("\\s+")).toSet()

    val WORD_RE = Regex("""[\p{L}]+(?:-[\p{L}]+)*""")

    fun wordKey(word: String): String {
        var w = Normalizer.normalize(word.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{Mn}+"), "")
        for (suffix in listOf("es", "s", "x", "e")) {
            if (w.length > 4 && w.endsWith(suffix)) {
                w = w.dropLast(suffix.length)
                break
            }
        }
        return w
    }

    data class Repetition(val key: String, val words: List<String>, val spans: List<IntRange>) {
        val count get() = spans.size
        val label get() = words.first().lowercase()
    }

    fun findRepetitions(text: String, window: Int = 40, minLen: Int = 4): List<Repetition> {
        data class Tok(val key: String, val word: String, val range: IntRange)
        val tokens = WORD_RE.findAll(text).map { m ->
            val w = m.value
            if (w.length < minLen || w.lowercase() in STOPWORDS) null else Tok(wordKey(w), w, m.range)
        }.toList()
        val positions = LinkedHashMap<String, MutableList<Int>>()
        tokens.forEachIndexed { i, t -> if (t != null) positions.getOrPut(t.key) { mutableListOf() }.add(i) }
        val result = mutableListOf<Repetition>()
        for ((key, idxs) in positions) {
            if (idxs.size < 2) continue
            val keep = sortedSetOf<Int>()
            for (k in 0 until idxs.size - 1) {
                if (idxs[k + 1] - idxs[k] <= window) { keep.add(idxs[k]); keep.add(idxs[k + 1]) }
            }
            if (keep.isEmpty()) continue
            val words = mutableListOf<String>()
            val spans = mutableListOf<IntRange>()
            for (i in keep) {
                val t = tokens[i]!!
                spans.add(t.range)
                if (words.none { it.equals(t.word, ignoreCase = true) }) words.add(t.word)
            }
            result.add(Repetition(key, words, spans))
        }
        return result.sortedWith(compareBy({ -it.count }, { it.spans.first().first }))
    }

    fun matchCase(original: String, replacement: String): String = when {
        original.length > 1 && original.all { !it.isLetter() || it.isUpperCase() } -> replacement.uppercase()
        original.firstOrNull()?.isUpperCase() == true -> replacement.replaceFirstChar { it.uppercaseChar() }
        else -> replacement
    }
}
