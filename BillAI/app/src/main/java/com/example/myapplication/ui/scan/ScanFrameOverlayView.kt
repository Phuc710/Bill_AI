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

class ScanFrameOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    private val overlayPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#3608141F")
        style = Paint.Style.FILL
    }

    private val framePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }

    private val accentPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }

    private val framePath = Path()
    private val frameRect = RectF()
    private var pulse = 0f
    private var visualState = ScanVisualState.DETECTING

    private val pulseAnimator = ValueAnimator.ofFloat(0f, 1f).apply {
        duration = 2200L
        repeatMode = ValueAnimator.REVERSE
        repeatCount = ValueAnimator.INFINITE
        addUpdateListener {
            pulse = it.animatedValue as Float
            invalidate()
        }
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        if (!pulseAnimator.isStarted) {
            pulseAnimator.start()
        }
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

        framePath.reset()
        framePath.fillType = Path.FillType.EVEN_ODD
        framePath.addRect(0f, 0f, width.toFloat(), height.toFloat(), Path.Direction.CW)
        framePath.addRoundRect(frameRect, cornerRadius(), cornerRadius(), Path.Direction.CW)
        canvas.drawPath(framePath, overlayPaint)

        val colors = stateColors(visualState)
        framePaint.color = colors.stroke
        framePaint.alpha = (210 + pulse * 40).toInt()
        framePaint.strokeWidth = dp(2.2f) + pulse * dp(0.6f)
        canvas.drawRoundRect(frameRect, cornerRadius(), cornerRadius(), framePaint)

        accentPaint.color = colors.accent
        accentPaint.alpha = (220 + pulse * 30).toInt()
        accentPaint.strokeWidth = dp(4.2f)
        drawCorners(canvas, accentPaint)
    }

    private fun drawCorners(canvas: Canvas, paint: Paint) {
        val cornerLength = frameRect.width() * 0.1f
        val radius = cornerRadius()

        canvas.drawLine(frameRect.left + radius * 0.55f, frameRect.top, frameRect.left + radius * 0.55f + cornerLength, frameRect.top, paint)
        canvas.drawLine(frameRect.left, frameRect.top + radius * 0.55f, frameRect.left, frameRect.top + radius * 0.55f + cornerLength, paint)

        canvas.drawLine(frameRect.right - radius * 0.55f, frameRect.top, frameRect.right - radius * 0.55f - cornerLength, frameRect.top, paint)
        canvas.drawLine(frameRect.right, frameRect.top + radius * 0.55f, frameRect.right, frameRect.top + radius * 0.55f + cornerLength, paint)

        canvas.drawLine(frameRect.left + radius * 0.55f, frameRect.bottom, frameRect.left + radius * 0.55f + cornerLength, frameRect.bottom, paint)
        canvas.drawLine(frameRect.left, frameRect.bottom - radius * 0.55f, frameRect.left, frameRect.bottom - radius * 0.55f - cornerLength, paint)

        canvas.drawLine(frameRect.right - radius * 0.55f, frameRect.bottom, frameRect.right - radius * 0.55f - cornerLength, frameRect.bottom, paint)
        canvas.drawLine(frameRect.right, frameRect.bottom - radius * 0.55f, frameRect.right, frameRect.bottom - radius * 0.55f - cornerLength, paint)
    }

    private fun updateFrameRect() {
        val frameWidth = width * 0.78f
        val frameHeight = min(height * 0.52f, frameWidth * 1.55f)
        val left = (width - frameWidth) / 2f
        val top = (height - frameHeight) / 2f - height * 0.05f
        frameRect.set(left, top, left + frameWidth, top + frameHeight)
    }

    private fun cornerRadius(): Float = dp(24f)

    private fun dp(value: Float): Float = value * resources.displayMetrics.density

    private fun stateColors(state: ScanVisualState): OverlayColors {
        return when (state) {
            ScanVisualState.DETECTING -> OverlayColors(
                stroke = Color.WHITE,
                accent = Color.WHITE
            )
            ScanVisualState.READY -> OverlayColors(
                stroke = ContextCompat.getColor(context, R.color.accent_mint),
                accent = ContextCompat.getColor(context, R.color.accent_mint)
            )
            ScanVisualState.WARNING -> OverlayColors(
                stroke = ContextCompat.getColor(context, R.color.warning_text),
                accent = ContextCompat.getColor(context, R.color.warning_text)
            )
            ScanVisualState.CAPTURED -> OverlayColors(
                stroke = ContextCompat.getColor(context, R.color.accent_sky),
                accent = ContextCompat.getColor(context, R.color.accent_sky)
            )
        }
    }

    private data class OverlayColors(
        val stroke: Int,
        val accent: Int
    )
}

enum class ScanVisualState {
    DETECTING,
    READY,
    WARNING,
    CAPTURED
}
