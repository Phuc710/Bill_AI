package com.example.myapplication.ui.scan

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View
import androidx.core.content.ContextCompat
import com.example.myapplication.R
import kotlin.math.min

/**
 * Premium scanner frame overlay.
 * - Dark semi-transparent overlay outside frame
 * - Thin border, bold corners only
 * - Pulse animation on corners
 * - Color states: WHITE (detecting) → MINT (ready) → AMBER (warning) → BLUE (captured)
 */
class ScanFrameOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    // Dark overlay outside scan area
    private val overlayPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#B0000000")
        style = Paint.Style.FILL
    }

    // Thin body border (full rect, very subtle)
    private val borderPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }

    // Bold corner accent lines
    private val cornerPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }

    private val framePath = Path()
    private val frameRect = RectF()

    private var pulse = 0f
    private var visualState = ScanVisualState.DETECTING

    private val pulseAnimator = ValueAnimator.ofFloat(0f, 1f).apply {
        duration = 1800L
        repeatMode = ValueAnimator.REVERSE
        repeatCount = ValueAnimator.INFINITE
        interpolator = android.view.animation.AccelerateDecelerateInterpolator()
        addUpdateListener {
            pulse = it.animatedValue as Float
            invalidate()
        }
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        if (!pulseAnimator.isStarted) pulseAnimator.start()
    }

    override fun onDetachedFromWindow() {
        pulseAnimator.cancel()
        super.onDetachedFromWindow()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        updateFrameRect()
    }

    fun setVisualState(state: ScanVisualState) {
        if (visualState == state) return
        visualState = state
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (frameRect.isEmpty) return

        val radius = cornerRadius()

        // ── 1. Dark overlay with cutout ───────────────────────────────
        framePath.reset()
        framePath.fillType = Path.FillType.EVEN_ODD
        framePath.addRect(0f, 0f, width.toFloat(), height.toFloat(), Path.Direction.CW)
        framePath.addRoundRect(frameRect, radius, radius, Path.Direction.CW)
        canvas.drawPath(framePath, overlayPaint)

        // ── 2. Very thin body border ──────────────────────────────────
        val colors = stateColors(visualState)
        borderPaint.color = colors.border
        borderPaint.alpha = (80 + pulse * 40).toInt()
        borderPaint.strokeWidth = dp(1f)
        canvas.drawRoundRect(frameRect, radius, radius, borderPaint)

        // ── 3. Bold corner accents ────────────────────────────────────
        val pulseAlpha = (210 + pulse * 45).toInt().coerceIn(0, 255)
        cornerPaint.color = colors.corner
        cornerPaint.alpha = pulseAlpha
        cornerPaint.strokeWidth = dp(3f) + pulse * dp(0.5f)
        drawCorners(canvas, cornerPaint, radius)
    }

    /**
     * Draw only the 4 corner L-shapes, not full rectangle.
     * Corner length = ~12% of frame width for clean look.
     */
    private fun drawCorners(canvas: Canvas, paint: Paint, radius: Float) {
        val arm = frameRect.width() * 0.10f   // length of each corner arm
        val inset = radius * 0.4f              // arc start offset

        val l = frameRect.left
        val t = frameRect.top
        val r = frameRect.right
        val b = frameRect.bottom

        // Top-left
        canvas.drawLine(l + inset, t, l + inset + arm, t, paint)
        canvas.drawLine(l, t + inset, l, t + inset + arm, paint)

        // Top-right
        canvas.drawLine(r - inset, t, r - inset - arm, t, paint)
        canvas.drawLine(r, t + inset, r, t + inset + arm, paint)

        // Bottom-left
        canvas.drawLine(l + inset, b, l + inset + arm, b, paint)
        canvas.drawLine(l, b - inset, l, b - inset - arm, paint)

        // Bottom-right
        canvas.drawLine(r - inset, b, r - inset - arm, b, paint)
        canvas.drawLine(r, b - inset, r, b - inset - arm, paint)
    }

    /**
     * Frame occupies 80% width, ratio ~1.45:1 (portrait bill).
     * Centered slightly above midpoint of screen.
     */
    private fun updateFrameRect() {
        val frameWidth  = width * 0.80f
        val frameHeight = min(height * 0.50f, frameWidth * 1.45f)
        val left = (width - frameWidth) / 2f
        val top  = (height - frameHeight) / 2f - height * 0.04f
        frameRect.set(left, top, left + frameWidth, top + frameHeight)
    }

    private fun cornerRadius(): Float = dp(20f)

    private fun dp(v: Float) = v * resources.displayMetrics.density

    private fun stateColors(state: ScanVisualState): Colors = when (state) {
        ScanVisualState.DETECTING -> Colors(border = 0x44FFFFFF, corner = Color.WHITE)
        ScanVisualState.READY     -> Colors(
            border = ContextCompat.getColor(context, R.color.accent_mint).withAlpha(80),
            corner = ContextCompat.getColor(context, R.color.accent_mint)
        )
        ScanVisualState.WARNING   -> Colors(
            border = Color.parseColor("#FFFBBF").withAlpha(80),
            corner = Color.parseColor("#FCD34D")
        )
        ScanVisualState.CAPTURED  -> Colors(
            border = ContextCompat.getColor(context, R.color.accent_sky).withAlpha(80),
            corner = ContextCompat.getColor(context, R.color.accent_sky)
        )
    }

    private fun Int.withAlpha(alpha: Int): Int {
        return Color.argb(alpha, Color.red(this), Color.green(this), Color.blue(this))
    }

    private data class Colors(val border: Int, val corner: Int)
}

enum class ScanVisualState {
    DETECTING,
    READY,
    WARNING,
    CAPTURED
}
