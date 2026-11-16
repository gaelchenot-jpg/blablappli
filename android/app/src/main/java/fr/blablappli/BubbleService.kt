package fr.blablappli

import android.Manifest
import android.accessibilityservice.AccessibilityService
import android.annotation.SuppressLint
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject
import org.vosk.Recognizer
import org.vosk.android.RecognitionListener
import org.vosk.android.SpeechService
import kotlin.math.abs

/**
 * Le cercle flottant de blablappli.
 *
 * C'est un service d'accessibilité : c'est ce qui lui permet d'afficher le
 * cercle par-dessus toutes les applis et d'écrire dans le champ de texte actif.
 */
class BubbleService : AccessibilityService(), RecognitionListener {

    companion object {
        private const val TAG = "blablappli"
        @Volatile var instance: BubbleService? = null
            private set
    }

    private lateinit var wm: WindowManager
    private val main = Handler(Looper.getMainLooper())
    private val dp get() = resources.displayMetrics.density

    private var bubble: JarvisView? = null
    private var bubbleParams: WindowManager.LayoutParams? = null
    private var caption: TextView? = null
    private var panel: LinearLayout? = null
    private var repRow: LinearLayout? = null
    private var synRow: LinearLayout? = null
    private var panelTitle: TextView? = null

    private var lastEditable: AccessibilityNodeInfo? = null
    private var speech: SpeechService? = null
    private var recognizer: Recognizer? = null
    private var listening = false
    private var online: OnlineRecognizer? = null
    private val buffer = StringBuilder()
    private var lastDictation = ""

    // ------------------------------------------------------------------ cycle de vie
    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        wm = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        Engine.init(this)
        showBubble()
        Engine.withModel(this) { m ->
            bubble?.state = if (m != null) JarvisView.State.IDLE else JarvisView.State.ERROR
            if (m == null) say("Modèle vocal introuvable : ${Engine.error}")
        }
    }

    override fun onDestroy() {
        stopListening(cancel = true)
        removeOverlays()
        instance = null
        super.onDestroy()
    }

    override fun onInterrupt() {}

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        val src = event?.source ?: return
        if (src.isEditable && src.packageName?.toString() != packageName) {
            lastEditable = src
        }
    }

    // ------------------------------------------------------------------ cercle
    private fun overlayParams(w: Int, h: Int, touchable: Boolean = true) = WindowManager.LayoutParams(
        w, h,
        WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
            (if (touchable) 0 else WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE),
        PixelFormat.TRANSLUCENT,
    ).apply { gravity = Gravity.TOP or Gravity.START }

    @SuppressLint("ClickableViewAccessibility")
    fun showBubble() {
        if (bubble != null) return
        val size = (110 * dp).toInt()
        val sp = getSharedPreferences("blablappli", MODE_PRIVATE)
        val metrics = resources.displayMetrics
        val params = overlayParams(size, size).apply {
            x = sp.getInt("bubble_x", metrics.widthPixels - size - (8 * dp).toInt())
            y = sp.getInt("bubble_y", (metrics.heightPixels * 0.55).toInt())
        }
        val v = JarvisView(this)
        v.continuous = Prefs.continuous(this)
        v.state = if (Engine.model != null) JarvisView.State.IDLE else JarvisView.State.LOADING

        var downX = 0f; var downY = 0f; var startX = 0; var startY = 0
        var dragging = false; var longPressed = false
        val longPress = Runnable {
            longPressed = true
            v.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
            togglePanel()
        }
        v.setOnTouchListener { _, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = e.rawX; downY = e.rawY; startX = params.x; startY = params.y
                    dragging = false; longPressed = false
                    main.postDelayed(longPress, 550)
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = e.rawX - downX; val dy = e.rawY - downY
                    if (!dragging && (abs(dx) > 12 * dp || abs(dy) > 12 * dp)) {
                        dragging = true
                        main.removeCallbacks(longPress)
                    }
                    if (dragging) {
                        params.x = startX + dx.toInt(); params.y = startY + dy.toInt()
                        wm.updateViewLayout(v, params)
                        placeCaption()
                    }
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    main.removeCallbacks(longPress)
                    if (dragging) {
                        sp.edit().putInt("bubble_x", params.x).putInt("bubble_y", params.y).apply()
                    } else if (!longPressed && e.actionMasked == MotionEvent.ACTION_UP) {
                        v.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                        toggleDictation()
                    }
                }
            }
            true
        }
        wm.addView(v, params)
        bubble = v
        bubbleParams = params

        val c = TextView(this).apply {
            setTextColor(Color.WHITE)
            textSize = 15f
            setPadding((12 * dp).toInt(), (8 * dp).toInt(), (12 * dp).toInt(), (8 * dp).toInt())
            background = GradientDrawable().apply { setColor(Color.parseColor("#E60F1720")); cornerRadius = 14 * dp }
            maxWidth = (260 * dp).toInt()
            visibility = View.GONE
        }
        wm.addView(c, overlayParams(WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT, touchable = false))
        caption = c
    }

    fun hideBubble() {
        stopListening(cancel = true)
        removeOverlays()
    }

    private fun removeOverlays() {
        for (view in listOfNotNull(bubble, caption, panel)) runCatching { wm.removeView(view) }
        bubble = null; caption = null; panel = null
    }

    private fun placeCaption() {
        val c = caption ?: return
        val p = bubbleParams ?: return
        val lp = c.layoutParams as? WindowManager.LayoutParams ?: return
        c.measure(View.MeasureSpec.UNSPECIFIED, View.MeasureSpec.UNSPECIFIED)
        val w = minOf(c.measuredWidth, (260 * dp).toInt())
        val screenW = resources.displayMetrics.widthPixels
        lp.x = (p.x + p.width / 2 - w / 2).coerceIn(0, maxOf(0, screenW - w))
        lp.y = maxOf(0, p.y - c.measuredHeight - (4 * dp).toInt())
        runCatching { wm.updateViewLayout(c, lp) }
    }

    /** Affiche un petit message au-dessus du cercle. */
    fun say(text: String, millis: Long = 3500) {
        val c = caption ?: return
        c.text = text
        c.visibility = if (text.isEmpty()) View.GONE else View.VISIBLE
        placeCaption()
        main.removeCallbacks(hideCaption)
        if (text.isNotEmpty() && millis > 0) main.postDelayed(hideCaption, millis)
    }

    private val hideCaption = Runnable { caption?.visibility = View.GONE }

    // ------------------------------------------------------------------ dictée
    fun toggleDictation() {
        if (listening) { stopListening(); return }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            say("Autorise d'abord le micro dans l'appli blablappli.")
            startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            return
        }
        if (Prefs.onlinePunctuation(this) && OnlineRecognizer.usable(this)) {
            startOnline()
            return
        }
        startOffline()
    }

    /** Dictée hors ligne (Vosk). */
    private fun startOffline() {
        if (Engine.model == null) {
            say("Le modèle vocal se prépare, encore un instant…")
            Engine.withModel(this) { m -> bubble?.state = if (m != null) JarvisView.State.IDLE else JarvisView.State.ERROR }
            return
        }
        bubble?.state = JarvisView.State.PROCESSING
        MicService.start(this)   // -> onMicReady
    }

    fun onMicReady(ok: Boolean, error: String?) = main.post {
        if (!ok) {
            bubble?.state = JarvisView.State.ERROR
            say("Impossible d'utiliser le micro : $error")
            return@post
        }
        try {
            val rec = Recognizer(Engine.model, 16000f)
            val s = SpeechService(rec, 16000f)
            recognizer = rec
            speech = s
            buffer.setLength(0)
            lastDictation = ""
            s.startListening(this)
            listening = true
            bubble?.badge = 0
            bubble?.state = JarvisView.State.LISTENING
            say("Je t'écoute…", 1500)
        } catch (e: Exception) {
            Log.e(TAG, "micro", e)
            MicService.stop(this)
            bubble?.state = JarvisView.State.ERROR
            say("Erreur micro : ${e.message}")
        }
    }

    /** Dictée en ligne (reconnaissance d'Android) : ponctuation automatique. */
    private fun startOnline() {
        buffer.setLength(0)
        lastDictation = ""
        val r = OnlineRecognizer(
            this,
            onPartial = { p ->
                bubble?.pulse()
                say((buffer.toString() + " " + p).trim().takeLast(120), 0)
            },
            onSegment = { t ->
                if (Prefs.continuous(this)) write(t)
                else {
                    buffer.append(TextTools.joinWith(buffer.toString(), t))
                    say(buffer.toString().takeLast(120), 0)
                }
            },
            onFinished = {
                online = null
                flushBuffer()
                say("", 0)
                bubble?.state = JarvisView.State.IDLE
            },
            onFailed = { why ->
                // pas de réseau ou service indisponible : on bascule hors ligne
                Log.w(TAG, "en ligne indisponible ($why), passage hors ligne")
                online = null
                flushBuffer()
                listening = false
                say("Connexion indisponible : dictée hors ligne (sans ponctuation auto).", 3000)
                startOffline()
            },
        )
        online = r
        listening = true
        bubble?.badge = 0
        bubble?.state = JarvisView.State.LISTENING
        say("Je t'écoute…", 1500)
        r.start()
    }

    private fun flushBuffer() {
        if (!Prefs.continuous(this) && buffer.isNotEmpty()) write(buffer.toString())
        buffer.setLength(0)
    }

    private fun stopListening(cancel: Boolean = false) {
        if (!listening) return
        listening = false
        bubble?.state = JarvisView.State.PROCESSING
        online?.let { r ->
            if (cancel) { r.cancel(); online = null; bubble?.state = JarvisView.State.IDLE } else r.stop()
            return
        }
        if (cancel) {
            speech?.cancel()
            cleanup()
        } else {
            speech?.stop() // -> onFinalResult
        }
    }

    private fun cleanup() {
        runCatching { speech?.shutdown() }
        runCatching { recognizer?.close() }
        speech = null
        recognizer = null
        MicService.stop(this)
        if (!listening) bubble?.state = if (Engine.model != null) JarvisView.State.IDLE else JarvisView.State.ERROR
    }

    private fun textOf(json: String?, key: String) =
        runCatching { JSONObject(json ?: "{}").optString(key, "") }.getOrDefault("").trim()

    override fun onPartialResult(hypothesis: String?) {
        val p = textOf(hypothesis, "partial")
        if (p.isNotEmpty()) {
            bubble?.pulse()
            say((buffer.toString() + " " + p).trim().takeLast(120), 0)
        }
    }

    override fun onResult(hypothesis: String?) {
        val t = textOf(hypothesis, "text")
        if (t.isEmpty()) return
        if (Prefs.continuous(this)) {
            write(t)
        } else {
            if (buffer.isNotEmpty()) buffer.append(' ')
            buffer.append(t)
            say(buffer.toString().takeLast(120), 0)
        }
    }

    override fun onFinalResult(hypothesis: String?) {
        val t = textOf(hypothesis, "text")
        if (Prefs.continuous(this)) {
            if (t.isNotEmpty()) write(t)
        } else {
            if (t.isNotEmpty()) { if (buffer.isNotEmpty()) buffer.append(' '); buffer.append(t) }
            if (buffer.isNotEmpty()) write(buffer.toString())
            buffer.setLength(0)
        }
        say("", 0)
        cleanup()
    }

    override fun onError(exception: Exception?) {
        Log.e(TAG, "reconnaissance", exception)
        listening = false
        cleanup()
        bubble?.state = JarvisView.State.ERROR
        say("Erreur : ${exception?.message}")
    }

    override fun onTimeout() { stopListening() }

    /** Écrit un morceau dicté dans le champ actif. */
    private fun write(raw: String) {
        val node = target()
        if (node == null) {
            copyToClipboard(raw)
            say("Aucun champ de texte actif : le texte est copié, tu peux le coller.")
            return
        }
        val text = currentText(node)
        val (s, e) = selection(node, text)
        val piece = TextTools.process(raw, text.substring(0, s), Prefs.voiceCommands(this))
        if (piece.isEmpty()) return
        replace(node, s, e, piece)
        lastDictation += piece
        val newText = currentText(node).ifEmpty { lastDictation }
        bubble?.badge = TextTools.findRepetitions(newText).size
    }

    // ------------------------------------------------------------------ champ de texte
    private fun target(): AccessibilityNodeInfo? {
        val focused = runCatching { rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT) }.getOrNull()
        if (focused != null && focused.isEditable) return focused
        val last = lastEditable ?: return null
        return if (last.refresh()) last else null
    }

    private fun currentText(node: AccessibilityNodeInfo): String {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && node.isShowingHintText) return ""
        return node.text?.toString() ?: ""
    }

    private fun selection(node: AccessibilityNodeInfo, text: String): Pair<Int, Int> {
        var s = node.textSelectionStart
        var e = node.textSelectionEnd
        if (s < 0 || s > text.length) s = text.length
        if (e < 0 || e > text.length) e = s
        return minOf(s, e) to maxOf(s, e)
    }

    private fun replace(node: AccessibilityNodeInfo, s: Int, e: Int, piece: String) {
        val text = currentText(node)
        val newText = text.substring(0, s) + piece + text.substring(e)
        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
        }
        val ok = node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
        if (ok) {
            setSelection(node, s + piece.length, s + piece.length)
        } else {
            // secours : coller
            setSelection(node, s, e)
            copyToClipboard(piece)
            node.performAction(AccessibilityNodeInfo.ACTION_PASTE)
        }
    }

    private fun setSelection(node: AccessibilityNodeInfo, a: Int, b: Int) {
        val args = Bundle().apply {
            putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT, a)
            putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT, b)
        }
        node.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION, args)
    }

    private fun copyToClipboard(text: String) {
        val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        cm.setPrimaryClip(ClipData.newPlainText("blablappli", text))
    }

    // ------------------------------------------------------------------ panneau (appui long)
    private fun togglePanel() {
        if (panel != null) { closePanel(); return }
        val p = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((12 * dp).toInt(), (10 * dp).toInt(), (12 * dp).toInt(), (12 * dp).toInt())
            background = GradientDrawable().apply { setColor(Color.parseColor("#F20F1720")); cornerRadius = 18 * dp; setStroke((1 * dp).toInt(), Color.parseColor("#2A6F8F")) }
        }
        val title = TextView(this).apply {
            setTextColor(Color.parseColor("#8FB3C9")); textSize = 13f
            text = "Sélectionne un mot, puis « Synonymes »."
        }
        panelTitle = title
        val buttons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        buttons.addView(button("Synonymes") { showSynonyms() })
        buttons.addView(button("Répétitions") { showRepetitions() })
        val cont = button(if (Prefs.continuous(this)) "Continu ✓" else "Continu") {}
        cont.setOnClickListener {
            val v = !Prefs.continuous(this)
            Prefs.setContinuous(this, v)
            bubble?.continuous = v
            (it as TextView).text = if (v) "Continu ✓" else "Continu"
        }
        buttons.addView(cont)
        buttons.addView(button("✕") { closePanel() })

        repRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        synRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        p.addView(title)
        p.addView(HorizontalScrollView(this).apply { addView(buttons) })
        p.addView(HorizontalScrollView(this).apply { addView(repRow) })
        p.addView(HorizontalScrollView(this).apply { addView(synRow) })

        val width = minOf(resources.displayMetrics.widthPixels - (16 * dp).toInt(), (420 * dp).toInt())
        val lp = overlayParams(width, WindowManager.LayoutParams.WRAP_CONTENT).apply {
            x = (resources.displayMetrics.widthPixels - width) / 2
            val by = bubbleParams?.y ?: 0
            y = if (by > resources.displayMetrics.heightPixels / 2) maxOf(0, by - (190 * dp).toInt()) else by + (115 * dp).toInt()
        }
        wm.addView(p, lp)
        panel = p
    }

    private fun closePanel() {
        panel?.let { runCatching { wm.removeView(it) } }
        panel = null
    }

    private fun button(label: String, onClick: () -> Unit) = TextView(this).apply {
        text = label
        setTextColor(Color.WHITE)
        textSize = 15f
        setPadding((14 * dp).toInt(), (9 * dp).toInt(), (14 * dp).toInt(), (9 * dp).toInt())
        background = GradientDrawable().apply { setColor(Color.parseColor("#1D7FA8")); cornerRadius = 12 * dp }
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT)
            .apply { setMargins(0, (8 * dp).toInt(), (8 * dp).toInt(), 0) }
        setOnClickListener { onClick() }
    }

    private fun chip(label: String, color: String, onClick: () -> Unit) = button(label, onClick).apply {
        background = GradientDrawable().apply { setColor(Color.parseColor(color)); cornerRadius = 16 * dp }
        setTextColor(Color.parseColor("#16202A"))
    }

    /** Mot sélectionné, ou mot sous le curseur : (début, fin, mot). */
    private fun wordAtCursor(node: AccessibilityNodeInfo): Triple<Int, Int, String>? {
        val text = currentText(node)
        val (s, e) = selection(node, text)
        if (e > s) {
            val w = text.substring(s, e).trim()
            if (w.isNotEmpty()) return Triple(s, e, w)
        }
        for (m in TextTools.WORD_RE.findAll(text)) {
            if (s >= m.range.first && s <= m.range.last + 1) return Triple(m.range.first, m.range.last + 1, m.value)
        }
        return null
    }

    private fun showSynonyms(range: Triple<Int, Int, String>? = null) {
        val row = synRow ?: return
        row.removeAllViews()
        val node = target()
        if (node == null) { panelTitle?.text = "Touche d'abord un champ de texte."; return }
        val (a, b, word) = range ?: wordAtCursor(node) ?: run {
            panelTitle?.text = "Sélectionne un mot (ou place le curseur dessus)."
            return
        }
        val syns = Engine.thesaurus.synonyms(word)
        if (syns.isEmpty()) { panelTitle?.text = "Pas de synonyme trouvé pour « $word »."; return }
        panelTitle?.text = "Synonymes de « $word » : touche pour remplacer"
        for (s in syns) {
            row.addView(chip(s, "#9FE3FF") {
                val n = target() ?: return@chip
                val text = currentText(n)
                // on vérifie que le mot est toujours au même endroit
                if (b <= text.length && text.substring(a, b) == word) {
                    replace(n, a, b, TextTools.matchCase(word, s))
                    panelTitle?.text = "« $word » → « $s »"
                    row.removeAllViews()
                    if (repRow?.childCount ?: 0 > 0) showRepetitions()
                }
            })
        }
    }

    private fun showRepetitions() {
        val row = repRow ?: return
        row.removeAllViews()
        synRow?.removeAllViews()
        val node = target()
        val text = node?.let { currentText(it) }.orEmpty()
        if (node == null || text.isBlank()) { panelTitle?.text = "Touche d'abord un champ de texte."; return }
        val reps = TextTools.findRepetitions(text)
        bubble?.badge = reps.size
        if (reps.isEmpty()) { panelTitle?.text = "Aucune répétition repérée 👍"; return }
        panelTitle?.text = "Mots répétés : touche un mot pour voir des synonymes"
        val colors = listOf("#FFD37A", "#C7F59B", "#FFB3C7", "#D9C2FF", "#FFCF9E", "#A8F0DC")
        reps.forEachIndexed { i, rep ->
            row.addView(chip("${rep.label} ×${rep.count}", colors[i % colors.size]) {
                val n = target() ?: return@chip
                // on sélectionne la 2e occurrence, en général celle qu'on veut changer
                val span = if (rep.spans.size > 1) rep.spans[1] else rep.spans[0]
                setSelection(n, span.first, span.last + 1)
                val t = currentText(n)
                showSynonyms(Triple(span.first, span.last + 1, t.substring(span.first, span.last + 1)))
            })
        }
    }
}
