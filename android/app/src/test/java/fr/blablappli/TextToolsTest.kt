package fr.blablappli

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream

class TextToolsTest {

    @Test fun ponctuationDictee() {
        assertEquals("bonjour, comment vas-tu ?", TextTools.applyVoiceCommands("bonjour virgule comment vas-tu point d'interrogation"))
        assertEquals("c'est fini.", TextTools.applyVoiceCommands("c'est fini point"))
        assertEquals("un point de vue", TextTools.applyVoiceCommands("un point de vue"))
        assertEquals("salut.\nà demain", TextTools.applyVoiceCommands("salut point à la ligne à demain"))
        assertEquals("un\n\ndeux", TextTools.applyVoiceCommands("un nouveau paragraphe deux"))
    }

    @Test fun enchainement() {
        assertEquals("Bonjour, ça va ?", TextTools.process("bonjour virgule ça va point d'interrogation", ""))
        assertEquals(" tu as raison.", TextTools.process("tu as raison point", "Je pense que"))
        assertEquals(" Demain on part.", TextTools.process("demain on part point", "C'est fini."))
        assertEquals("Salut.\nÀ demain", TextTools.process("salut point à la ligne à demain", ""))
        assertEquals(",", TextTools.process("virgule", "Bonjour"))
        // texte déjà ponctué par la reconnaissance en ligne
        assertEquals(" tu as raison.", TextTools.process("Tu as raison.", "Je pense que"))
        assertEquals(" Paris est loin ?", TextTools.process("Paris est loin ?", "Bonjour."))
    }

    @Test fun repetitions() {
        val reps = TextTools.findRepetitions("Le chat est très beau. Le chat dort sur le canapé, et les chats aiment dormir.")
        val chat = reps.first { it.key == "chat" }
        assertEquals(3, chat.count)
        assertTrue(reps.none { it.key == "le" })
    }

    @Test fun casse() {
        assertEquals("Demeure", TextTools.matchCase("Maison", "demeure"))
        assertEquals("demeure", TextTools.matchCase("maison", "demeure"))
    }

    @Test fun thesaurus() {
        val data = "UTF-8\nmaison|2\n(nom)|demeure|habitation|logis\n(nom)|famille|lignée\nrapide|1\n(adj)|prompt|vif|véloce (soutenu)\n"
        val t = Thesaurus { ByteArrayInputStream(data.toByteArray()) }
        assertEquals(listOf("demeure", "habitation"), t.synonyms("maison").take(2))
        assertEquals("Demeure", t.synonyms("Maisons").first())
        assertTrue("véloce" in t.synonyms("rapides"))
    }
}
