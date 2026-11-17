package fr.blablappli

import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Correction de grammaire et de mots confondus avec LanguageTool
 * (service public gratuit, sans compte ni clé). Utilisé seulement quand le
 * téléphone a internet ; en cas d'échec, le texte est écrit tel quel.
 */
object LanguageTool {
    private const val URL_CHECK = "https://api.languagetool.org/v2/check"

    // Règles ignorées : typographie, style, majuscule de début (gérée par l'appli)
    private val SKIP_CATEGORIES = setOf("TYPOGRAPHY", "STYLE", "REDUNDANCY", "CASING", "PUNCTUATION")
    private val SKIP_RULES = listOf("UPPERCASE_SENTENCE_START", "WHITESPACE", "APOS", "ESPACE", "FRENCH_WORD_REPEAT")

    fun correct(text: String, timeoutMs: Int = 4000): String {
        if (text.isBlank()) return text
        return try {
            val body = "language=fr&text=" + URLEncoder.encode(text, "UTF-8")
            val conn = (URL(URL_CHECK).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = timeoutMs
                readTimeout = timeoutMs
                doOutput = true
                setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
                setRequestProperty("Accept", "application/json")
            }
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            if (conn.responseCode != 200) {
                Log.w("blablappli", "LanguageTool : code ${conn.responseCode}")
                return text
            }
            val json = conn.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            apply(text, json)
        } catch (e: Exception) {
            Log.w("blablappli", "LanguageTool indisponible : ${e.message}")
            text
        }
    }

    /** Applique la première suggestion de chaque erreur retenue. Séparé pour les tests. */
    fun apply(text: String, json: String): String {
        val matches = JSONObject(json).optJSONArray("matches") ?: return text
        data class Edit(val start: Int, val end: Int, val repl: String)
        val edits = mutableListOf<Edit>()
        for (i in 0 until matches.length()) {
            val m = matches.getJSONObject(i)
            val rule = m.optJSONObject("rule") ?: continue
            val ruleId = rule.optString("id")
            val category = rule.optJSONObject("category")?.optString("id").orEmpty()
            if (category in SKIP_CATEGORIES || SKIP_RULES.any { ruleId.contains(it) }) continue
            val reps = m.optJSONArray("replacements") ?: continue
            if (reps.length() == 0) continue
            val repl = reps.getJSONObject(0).optString("value")
            val start = m.optInt("offset", -1)
            val end = start + m.optInt("length", 0)
            if (start < 0 || end > text.length || end <= start) continue
            val original = text.substring(start, end)
            // nom propre probable (majuscule au milieu du texte) : on n'y touche pas
            if (rule.optString("issueType") == "misspelling" && original.firstOrNull()?.isUpperCase() == true && start > 0) continue
            edits.add(Edit(start, end, repl))
        }
        var out = text
        var lastStart = Int.MAX_VALUE
        for (e in edits.sortedByDescending { it.start }) {
            if (e.end > lastStart) continue
            out = out.substring(0, e.start) + e.repl + out.substring(e.end)
            lastStart = e.start
        }
        return out
    }
}
