package fr.blablappli

import java.io.InputStream
import java.nio.charset.Charset

/** Synonymes à partir du thésaurus libre de LibreOffice (format MyThes). */
class Thesaurus(private val open: () -> InputStream?) {

    private var index: Map<String, List<Pair<String, List<String>>>>? = null

    @Synchronized
    private fun ensureLoaded(): Map<String, List<Pair<String, List<String>>>> {
        index?.let { return it }
        val map = HashMap<String, MutableList<Pair<String, List<String>>>>(70000)
        val stream = open()
        if (stream != null) {
            val bytes = stream.use { it.readBytes() }
            val nl = bytes.indexOf('\n'.code.toByte()).coerceAtLeast(0)
            var enc = String(bytes, 0, nl, Charsets.US_ASCII).trim()
            if (enc.isEmpty() || enc.uppercase().replace("-", "") == "ISO88591") enc = if (enc.isEmpty()) "UTF-8" else "ISO-8859-1"
            val lines = String(bytes, nl + 1, bytes.size - nl - 1, Charset.forName(enc)).lines()
            var i = 0
            while (i < lines.size) {
                val head = lines[i++]
                val bar = head.lastIndexOf('|')
                if (bar <= 0) continue
                val n = head.substring(bar + 1).trim().toIntOrNull() ?: continue
                val word = head.substring(0, bar).lowercase()
                val meanings = map.getOrPut(word) { mutableListOf() }
                for (line in lines.subList(i, minOf(i + n, lines.size))) {
                    val parts = line.split('|')
                    val pos = parts.first().trim('(', ')', ' ')
                    val syns = parts.drop(1).map { clean(it) }.filter { it.isNotEmpty() }
                    if (syns.isNotEmpty()) meanings.add(pos to syns)
                }
                i += n
            }
        }
        index = map
        return map
    }

    val available: Boolean get() = ensureLoaded().isNotEmpty()

    fun lookup(word: String): List<Pair<String, List<String>>> {
        val idx = ensureLoaded()
        val w = word.trim().lowercase()
        val candidates = mutableListOf(w)
        for ((suf, rep) in listOf("s" to "", "x" to "", "es" to "", "e" to "", "aux" to "al", "euses" to "eux", "euse" to "eux")) {
            if (w.endsWith(suf) && w.length > suf.length + 2) candidates.add(w.dropLast(suf.length) + rep)
        }
        for (c in candidates) idx[c]?.let { if (it.isNotEmpty()) return it }
        return emptyList()
    }

    fun synonyms(word: String, limit: Int = 30): List<String> {
        val seen = HashSet<String>()
        val out = mutableListOf<String>()
        for ((_, syns) in lookup(word)) for (s in syns) {
            val l = s.lowercase()
            if (l == word.lowercase() || !seen.add(l)) continue
            out.add(TextTools.matchCase(word, s))
            if (out.size >= limit) return out
        }
        return out
    }

    private fun clean(s: String): String = s.substringBefore('(').trim()
}
