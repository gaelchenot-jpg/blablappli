package fr.blablappli

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader
import android.view.View
import kotlin.math.min
import kotlin.math.sin

/** Le cercle "Jarvis" : anneaux qui tournent, halo qui respire quand on parle. */
class JarvisView(ctx: Context) : View(ctx) {

    enum class State { LOADING, IDLE, LISTENING, PROCESSING, ERROR }

    var state = State.LOADING
        set(v) { field = v; invalidate() }
    var continuous = false
        set(v) { field = v; invalidate() }
    var badge = 0
        set(v) { field = v; invalidate() }
    /** Petit "coup" d'énergie quand un mot est reconnu, pour animer le halo. */
    fun pulse() { energy = 1f }

    private var energy = 0f
    private var angle = 0f
    private val start = System.nanoTime()
    private val dp = resources.displayMetrics.density

    private val ring = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND }
    private val dashed = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE }
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
    private val text = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.WHITE; textAlign = Paint.Align.CENTER; isFakeBoldText = true }
    private val rect = RectF()

    private fun colors(): Pair<Int, Int> = when (state) {
        State.LOADING -> Color.parseColor("#7D8B99") to Color.parseColor("#3A4550")
        State.IDLE -> Color.parseColor("#39D0FF") to Color.parseColor("#0D3550")
        State.LISTENING -> Color.parseColor("#5FF3FF") to Color.parseColor("#0A6C9A")
        State.PROCESSING -> Color.parseColor("#FFC35C") to Color.parseColor("#6A4300")
        State.ERROR -> Color.parseColor("#FF5C6C") to Color.parseColor("#5A0D16")
    }

    override fun onDraw(c: Canvas) {
        val (main, dark) = colors()
        val cx = width / 2f
        val cy = height / 2f
        val r = min(width, height) / 2f - 18 * dp
        val t = (System.nanoTime() - start) / 1e9f
        val speed = when (state) {
            State.LOADING -> 4f; State.IDLE -> 0.6f; State.LISTENING -> 3.2f; State.PROCESSING -> 7f; State.ERROR -> 0f
        }
        angle = (angle + speed) % 360f
        energy *= 0.93f

        // halo
        val listening = state == State.LISTENING
        val wave = if (listening) 0.35f + 0.25f * sin(t * 6f) + energy * 0.6f else 0.15f + 0.1f * sin(t * 2.2f)
        val glowR = r + 6 * dp + wave * 14 * dp
        fill.shader = RadialGradient(cx, cy, glowR, intArrayOf(withAlpha(main, if (listening) 120 else 60), withAlpha(main, 0)),
            floatArrayOf(0.6f, 1f), Shader.TileMode.CLAMP)
        c.drawCircle(cx, cy, glowR, fill)

        // disque
        fill.shader = RadialGradient(cx - r * 0.3f, cy - r * 0.3f, r * 1.3f,
            intArrayOf(withAlpha(main, 235), dark, Color.parseColor("#050B12")), floatArrayOf(0f, 0.55f, 1f), Shader.TileMode.CLAMP)
        c.drawCircle(cx, cy, r * 0.78f, fill)
        fill.shader = null

        // anneau extérieur
        ring.color = main
        ring.strokeWidth = 3.5f * dp
        rect.set(cx - r, cy - r, cx + r, cy + r)
        for (k in 0 until 3) c.drawArc(rect, angle + k * 120, 70f, false, ring)

        // anneau intérieur en pointillés
        dashed.color = withAlpha(main, 150)
        dashed.strokeWidth = 1.5f * dp
        dashed.pathEffect = DashPathEffect(floatArrayOf(2 * dp, 4 * dp), -angle * 1.6f * dp)
        c.drawCircle(cx, cy, r * 0.9f, dashed)

        drawMic(c, cx, cy, r * 0.36f)

        if (continuous) pill(c, cx + r * 0.72f, cy + r * 0.72f, "∞", Color.parseColor("#1FD18B"))
        if (badge > 0) pill(c, cx + r * 0.72f, cy - r * 0.72f, badge.toString(), Color.parseColor("#FF9A3C"))

        postInvalidateOnAnimation()
    }

    private fun drawMic(c: Canvas, cx: Float, cy: Float, s: Float) {
        val color = if (state == State.LOADING) Color.parseColor("#C8D0D8") else Color.parseColor("#EAFCFF")
        ring.color = color
        ring.strokeWidth = maxOf(1.6f * dp, s * 0.16f)
        rect.set(cx - s * 0.38f, cy - s * 0.95f, cx + s * 0.38f, cy + s * 0.3f)
        if (state == State.LISTENING) {
            fill.color = color
            c.drawRoundRect(rect, s * 0.38f, s * 0.38f, fill)
        }
        c.drawRoundRect(rect, s * 0.38f, s * 0.38f, ring)
        rect.set(cx - s * 0.7f, cy - s * 0.6f, cx + s * 0.7f, cy + s * 0.6f)
        c.drawArc(rect, 20f, 140f, false, ring)
        c.drawLine(cx, cy + s * 0.6f, cx, cy + s * 0.95f, ring)
    }

    private fun pill(c: Canvas, x: Float, y: Float, label: String, color: Int) {
        fill.color = color
        c.drawCircle(x, y, 12 * dp, fill)
        text.textSize = 12 * dp
        c.drawText(label, x, y + 4 * dp, text)
    }

    private fun withAlpha(color: Int, a: Int) = Color.argb(a, Color.red(color), Color.green(color), Color.blue(color))
}
