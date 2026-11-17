package fr.blablappli

import android.Manifest
import android.app.Activity
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.ViewGroup
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/** Écran de réglage : autorisations, options, zone d'essai. */
class MainActivity : Activity() {

    private val dp get() = resources.displayMetrics.density
    private lateinit var micStatus: TextView
    private lateinit var a11yStatus: TextView
    private lateinit var modelStatus: TextView
    private lateinit var showBubbleBtn: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Engine.init(this)

        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(px(20), px(28), px(20), px(28))
        }
        col.addView(JarvisView(this).apply {
            state = JarvisView.State.IDLE
            layoutParams = LinearLayout.LayoutParams(px(130), px(130)).apply { gravity = Gravity.CENTER_HORIZONTAL }
        })
        col.addView(text("blablappli", 28f, "#EAFCFF", bold = true).apply { gravity = Gravity.CENTER })
        col.addView(text("Dictée vocale en français, dans toutes tes applis, sans internet.", 15f, "#8FB3C9").apply {
            gravity = Gravity.CENTER; setPadding(0, 0, 0, px(18))
        })

        // Étape 1
        col.addView(section("1. Autoriser le micro"))
        micStatus = text("", 14f, "#8FB3C9")
        col.addView(micStatus)
        col.addView(button("Autoriser le micro") {
            val perms = mutableListOf(Manifest.permission.RECORD_AUDIO)
            if (Build.VERSION.SDK_INT >= 33) perms.add(Manifest.permission.POST_NOTIFICATIONS)
            requestPermissions(perms.toTypedArray(), 1)
        })

        // Étape 2
        col.addView(section("2. Activer le cercle"))
        a11yStatus = text("", 14f, "#8FB3C9")
        col.addView(a11yStatus)
        col.addView(text(
            "Dans la page qui s'ouvre, touche « blablappli » (parfois rangé dans « Applications installées » " +
                "ou « Services installés ») et active-le.\n\n" +
                "Si l'interrupteur est grisé (« paramètre restreint ») : touche le bouton « Infos de l'appli » " +
                "ci-dessous, puis les ⋮ en haut à droite, puis « Autoriser les paramètres restreints », et recommence.",
            13f, "#B9CCD9",
        ))
        col.addView(button("Ouvrir les réglages d'accessibilité") {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        })
        col.addView(button("Infos de l'appli", secondary = true) {
            startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName")))
        })
        showBubbleBtn = button("Afficher le cercle", secondary = true) {
            val svc = BubbleService.instance
            if (svc == null) {
                // activé dans les réglages, mais le service ne tourne pas (arrêté par Android)
                android.widget.Toast.makeText(
                    this,
                    "Le cercle n'est pas démarré. Dans la page qui s'ouvre, désactive puis réactive blablappli.",
                    android.widget.Toast.LENGTH_LONG,
                ).show()
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            } else {
                val err = svc.showBubble()
                android.widget.Toast.makeText(
                    this,
                    err?.let { "Impossible d'afficher le cercle : $it" } ?: "Le cercle est affiché sur le côté droit de l'écran.",
                    android.widget.Toast.LENGTH_LONG,
                ).show()
                if (err == null) moveTaskToBack(true)
            }
        }
        col.addView(showBubbleBtn)

        // Options
        col.addView(section("Options"))
        col.addView(check("Ponctuation automatique quand le téléphone a internet (reconnaissance Google) ; sinon dictée hors ligne", Prefs.onlinePunctuation(this)) {
            Prefs.setOnlinePunctuation(this, it)
        })
        col.addView(check("Correction automatique des fautes et des mots mal compris quand le téléphone a internet (LanguageTool, gratuit)", Prefs.onlineCorrection(this)) {
            Prefs.setOnlineCorrection(this, it)
        })
        col.addView(check("Dictée continue (le texte s'écrit à chaque pause)", Prefs.continuous(this)) {
            Prefs.setContinuous(this, it)
        })
        col.addView(check("Commandes vocales (« virgule », « point », « à la ligne »…)", Prefs.voiceCommands(this)) {
            Prefs.setVoiceCommands(this, it)
        })

        // Mode d'emploi
        col.addView(section("Comment ça marche"))
        col.addView(text(
            "• Touche un champ de texte, puis touche le cercle et parle. Touche-le encore pour arrêter.\n" +
                "• Fais glisser le cercle pour le déplacer.\n" +
                "• Appui long sur le cercle : synonymes du mot sélectionné, répétitions, dictée continue.\n" +
                "• La pastille orange indique le nombre de mots répétés.\n\n" +
                "Avec internet, la ponctuation se met toute seule. Hors ligne, dis « virgule », « point », « point d'interrogation », « point d'exclamation », " +
                "« deux points », « à la ligne », « point à la ligne », « nouveau paragraphe », " +
                "« ouvrez les guillemets »… Les majuscules en début de phrase sont automatiques.",
            14f, "#D5E3EC",
        ))

        // Essai
        col.addView(section("Essaie ici"))
        modelStatus = text("", 13f, "#8FB3C9")
        col.addView(modelStatus)
        col.addView(EditText(this).apply {
            hint = "Touche ici, puis le cercle, et parle…"
            minLines = 4
            gravity = Gravity.TOP
            setTextColor(Color.parseColor("#16202A"))
            setHintTextColor(Color.parseColor("#7A8A96"))
            background = GradientDrawable().apply { setColor(Color.parseColor("#F9FBFC")); cornerRadius = 10 * dp }
            setPadding(px(12), px(12), px(12), px(12))
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
                .apply { topMargin = px(8) }
        })

        setContentView(ScrollView(this).apply {
            setBackgroundColor(Color.parseColor("#0F1720"))
            addView(col)
        })
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        refresh()
    }

    private fun refresh() {
        val mic = checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        micStatus.text = if (mic) "✓ Micro autorisé" else "Pas encore autorisé"
        micStatus.setTextColor(Color.parseColor(if (mic) "#1FD18B" else "#FFC35C"))

        val on = accessibilityEnabled()
        a11yStatus.text = if (on) "✓ Cercle activé" else "Pas encore activé"
        a11yStatus.setTextColor(Color.parseColor(if (on) "#1FD18B" else "#FFC35C"))
        showBubbleBtn.visibility = if (on) android.view.View.VISIBLE else android.view.View.GONE

        modelStatus.text = when {
            Engine.model != null -> "✓ Reconnaissance vocale prête"
            Engine.error != null -> "Problème avec le modèle vocal : ${Engine.error}"
            else -> "Préparation de la reconnaissance vocale (la première fois, ~30 s)…"
        }
        if (Engine.model == null) Engine.withModel(this) { refresh() }
    }

    private fun accessibilityEnabled(): Boolean {
        val enabled = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: return false
        val me = ComponentName(this, BubbleService::class.java)
        return enabled.split(':').any {
            ComponentName.unflattenFromString(it)?.let { c -> c == me } ?: false
        }
    }

    // --- petits composants -----------------------------------------------------------
    private fun px(v: Int) = (v * dp).toInt()

    private fun text(s: String, size: Float, color: String, bold: Boolean = false) = TextView(this).apply {
        text = s
        textSize = size
        setTextColor(Color.parseColor(color))
        if (bold) typeface = Typeface.DEFAULT_BOLD
        setLineSpacing(0f, 1.15f)
    }

    private fun section(s: String) = text(s, 18f, "#39D0FF", bold = true).apply { setPadding(0, px(22), 0, px(6)) }

    private fun button(label: String, secondary: Boolean = false, onClick: () -> Unit) = TextView(this).apply {
        text = label
        textSize = 16f
        gravity = Gravity.CENTER
        setTextColor(Color.WHITE)
        setPadding(px(16), px(13), px(16), px(13))
        background = GradientDrawable().apply {
            setColor(Color.parseColor(if (secondary) "#2A3744" else "#1D7FA8")); cornerRadius = 12 * dp
        }
        layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            .apply { topMargin = px(10) }
        setOnClickListener { onClick() }
    }

    private fun check(label: String, value: Boolean, onChange: (Boolean) -> Unit) = CheckBox(this).apply {
        text = label
        textSize = 15f
        isChecked = value
        setTextColor(Color.parseColor("#D5E3EC"))
        setOnCheckedChangeListener { _, v -> onChange(v) }
    }
}
