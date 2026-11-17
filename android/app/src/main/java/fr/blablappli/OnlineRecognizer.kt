package fr.blablappli

import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log

/**
 * Reconnaissance en ligne d'Android (Google), utilisée quand le téléphone a
 * internet : elle met la ponctuation et les majuscules toute seule.
 *
 * La reconnaissance d'Android s'arrête d'elle-même après un silence ; on la
 * relance tant que l'utilisateur n'a pas touché le cercle pour arrêter.
 */
class OnlineRecognizer(
    private val ctx: Context,
    private val onPartial: (String) -> Unit,
    private val onSegment: (String) -> Unit,
    private val onFinished: () -> Unit,
    private val onFailed: (String) -> Unit,
) : RecognitionListener {

    companion object {
        fun usable(ctx: Context): Boolean =
            SpeechRecognizer.isRecognitionAvailable(ctx) && hasInternet(ctx)

        fun hasInternet(ctx: Context): Boolean {
            val cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
            return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
                caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
        }
    }

    private var sr: SpeechRecognizer? = null
    private var wanted = false        // l'utilisateur veut continuer à dicter
    private var gotSomething = false  // au moins un mot reconnu depuis le début

    fun start() {
        wanted = true
        listenOnce()
    }

    /** Arrêt demandé : le dernier morceau arrive encore dans onResults. */
    fun stop() {
        wanted = false
        sr?.stopListening()
    }

    fun cancel() {
        wanted = false
        release()
    }

    private fun listenOnce() {
        release()
        val r = SpeechRecognizer.createSpeechRecognizer(ctx)
        r.setRecognitionListener(this)
        sr = r
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "fr-FR")
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "fr-FR")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, false)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, ctx.packageName)
            // pauses plus longues avant de couper
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 2500L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 2000L)
            if (Build.VERSION.SDK_INT >= 33) {
                // ponctuation et majuscules automatiques
                putExtra(RecognizerIntent.EXTRA_ENABLE_FORMATTING, RecognizerIntent.FORMATTING_OPTIMIZE_QUALITY)
            }
        }
        r.startListening(intent)
    }

    private fun release() {
        runCatching { sr?.destroy() }
        sr = null
    }

    private fun best(b: Bundle?): String =
        b?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.trim().orEmpty()

    override fun onPartialResults(partialResults: Bundle?) {
        val t = best(partialResults)
        if (t.isNotEmpty()) onPartial(t)
    }

    override fun onResults(results: Bundle?) {
        val t = best(results)
        if (t.isNotEmpty()) { gotSomething = true; onSegment(t) }
        continueOrFinish()
    }

    override fun onError(error: Int) {
        Log.w("blablappli", "reconnaissance en ligne : erreur $error")
        when (error) {
            SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> continueOrFinish()
            SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT,
            SpeechRecognizer.ERROR_SERVER, 12 /* langue non prise en charge */, 13 /* langue indisponible */,
            SpeechRecognizer.ERROR_RECOGNIZER_BUSY, SpeechRecognizer.ERROR_CLIENT -> {
                if (!wanted) { release(); onFinished() } else { wanted = false; release(); onFailed("erreur $error") }
            }
            else -> { wanted = false; release(); onFailed("erreur $error") }
        }
    }

    private fun continueOrFinish() {
        if (wanted) listenOnce() else { release(); onFinished() }
    }

    override fun onReadyForSpeech(params: Bundle?) {}
    override fun onBeginningOfSpeech() {}
    override fun onRmsChanged(rmsdB: Float) {}
    override fun onBufferReceived(buffer: ByteArray?) {}
    override fun onEndOfSpeech() {}
    override fun onEvent(eventType: Int, params: Bundle?) {}
}
