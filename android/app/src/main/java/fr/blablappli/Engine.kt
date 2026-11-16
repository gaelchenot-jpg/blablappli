package fr.blablappli

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import org.vosk.LibVosk
import org.vosk.LogLevel
import org.vosk.Model
import org.vosk.android.StorageService

/** Charge une seule fois le modèle vocal et le thésaurus, partagés par l'appli et le clavier. */
object Engine {
    private const val TAG = "blablappli"

    @Volatile var model: Model? = null
        private set
    @Volatile var error: String? = null
        private set
    private var loading = false
    private val waiting = mutableListOf<(Model?) -> Unit>()
    private val main = Handler(Looper.getMainLooper())

    lateinit var thesaurus: Thesaurus
        private set

    fun init(ctx: Context) {
        val app = ctx.applicationContext
        if (!::thesaurus.isInitialized) {
            thesaurus = Thesaurus {
                try { app.assets.open("thes_fr.dat") } catch (e: Exception) { null }
            }
            // chargement en arrière-plan pour que les synonymes soient instantanés
            Thread { runCatching { thesaurus.available } }.start()
        }
    }

    /** Appelle [done] (sur le fil principal) quand le modèle est prêt, ou avec null en cas d'échec. */
    fun withModel(ctx: Context, done: (Model?) -> Unit) {
        init(ctx)
        model?.let { done(it); return }
        synchronized(this) {
            waiting.add(done)
            if (loading) return
            loading = true
        }
        try { LibVosk.setLogLevel(LogLevel.WARNINGS) } catch (_: Throwable) {}
        StorageService.unpack(
            ctx.applicationContext, "model-fr", "model",
            { m ->
                model = m
                error = null
                flush(m)
            },
            { e ->
                Log.e(TAG, "Modèle vocal", e)
                error = e.message ?: e.toString()
                flush(null)
            },
        )
    }

    private fun flush(m: Model?) {
        val list: List<(Model?) -> Unit>
        synchronized(this) {
            list = waiting.toList()
            waiting.clear()
            loading = false
        }
        main.post { list.forEach { it(m) } }
    }
}

object Prefs {
    private fun sp(ctx: Context) = ctx.getSharedPreferences("blablappli", Context.MODE_PRIVATE)
    fun continuous(ctx: Context) = sp(ctx).getBoolean("continuous", false)
    fun setContinuous(ctx: Context, v: Boolean) = sp(ctx).edit().putBoolean("continuous", v).apply()
    fun voiceCommands(ctx: Context) = sp(ctx).getBoolean("voice_commands", true)
    fun setVoiceCommands(ctx: Context, v: Boolean) = sp(ctx).edit().putBoolean("voice_commands", v).apply()
    /** En ligne : reconnaissance d'Android, avec ponctuation automatique. */
    fun onlinePunctuation(ctx: Context) = sp(ctx).getBoolean("online", true)
    fun setOnlinePunctuation(ctx: Context, v: Boolean) = sp(ctx).edit().putBoolean("online", v).apply()
}
