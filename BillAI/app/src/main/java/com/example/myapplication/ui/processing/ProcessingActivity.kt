package com.example.myapplication.ui.processing

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.bumptech.glide.Glide
import com.example.myapplication.R
import com.example.myapplication.data.bootstrap.AppSessionStore
import com.example.myapplication.data.repository.AuthRepository
import com.example.myapplication.data.repository.BillRepository
import com.example.myapplication.databinding.ActivityProcessingBinding
import com.example.myapplication.ui.bills.BillDetailActivity
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream

class ProcessingActivity : AppCompatActivity() {

    private lateinit var binding: ActivityProcessingBinding
    private val billRepository = BillRepository()
    private val authRepository = AuthRepository()
    private var progressJob: Job? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        binding = ActivityProcessingBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnCancel.setOnClickListener { finish() }

        val imageUri = intent.getStringExtra(EXTRA_IMAGE_URI)?.let(Uri::parse) ?: run {
            finish()
            return
        }

        renderCapturedPreview(imageUri)
        playEntranceAnimation()
        uploadBill(imageUri)
    }

    private fun renderCapturedPreview(imageUri: Uri) {
        Glide.with(this).load(imageUri).centerCrop().into(binding.ivCapturedPreview)
    }

    private fun playEntranceAnimation() {
        binding.viewProcessingScrim.animate().alpha(1f).setDuration(300L).start()
        binding.cardProcessing.animate()
            .translationY(0f)
            .alpha(1f)
            .setDuration(360L)
            .setStartDelay(80L)
            .start()
    }

    private fun uploadBill(imageUri: Uri) {
        lifecycleScope.launch {
            val userId = authRepository.getUserId()
            if (userId.isNullOrBlank()) {
                Toast.makeText(this@ProcessingActivity,
                    getString(R.string.processing_error_session), Toast.LENGTH_SHORT).show()
                finish()
                return@launch
            }

            progressJob = launchPipelineSteps()
            val imageFile = copyUriToTempFile(imageUri)

            billRepository.extractBill(imageFile, userId).fold(
                onSuccess = { result ->
                    progressJob?.cancel()
                    AppSessionStore.invalidate()
                    // Step 3 complete
                    setStep(progress = 100, stepText = "Hoàn tất!")
                    delay(280L)
                    startActivity(BillDetailActivity.createIntent(this@ProcessingActivity, result.bill_id, startInEditMode = true))
                    finish()
                },
                onFailure = { error ->
                    progressJob?.cancel()
                    Toast.makeText(
                        this@ProcessingActivity,
                        getString(R.string.processing_error_failed, error.message ?: ""),
                        Toast.LENGTH_LONG
                    ).show()
                    finish()
                }
            )
        }
    }

    /**
     * 3 clean steps:
     * 1. Đang tải ảnh lên      (0 → 30%)
     * 2. Đang xử lý hóa đơn   (30 → 75%)
     * 3. (done) → set by onSuccess
     */
    private fun launchPipelineSteps(): Job {
        return lifecycleScope.launch {
            setStep(progress = 0,  stepText = "Đang tải ảnh lên...")
            delay(1000L)
            animateProgress(0, 30)

            setStep(progress = 30, stepText = "Đang phân tích dữ liệu...")
            delay(800L)
            animateProgress(30, 75)

            // Stay here until actual API returns
            delay(Long.MAX_VALUE)
        }
    }

    private fun setStep(progress: Int, stepText: String) {
        binding.progressIndicator.progress = progress

        // Animate step text
        binding.tvCurrentStep.animate().alpha(0f).setDuration(120L).withEndAction {
            binding.tvCurrentStep.text = stepText
            binding.tvCurrentStep.alpha = 1f
        }.start()
    }

    private suspend fun animateProgress(from: Int, to: Int) {
        val steps = (to - from)
        val delayPerStep = 500L / steps.coerceAtLeast(1)
        for (i in from..to) {
            binding.progressIndicator.progress = i
            delay(delayPerStep)
        }
    }

    private fun copyUriToTempFile(uri: Uri): File {
        val tempFile = File.createTempFile("bill_upload_", ".jpg", cacheDir)
        val inputStream = if (uri.scheme == "file") {
            FileInputStream(File(requireNotNull(uri.path)))
        } else {
            contentResolver.openInputStream(uri)
        }
        inputStream?.use { input ->
            FileOutputStream(tempFile).use { output -> input.copyTo(output) }
        }
        return tempFile
    }

    companion object {
        private const val EXTRA_IMAGE_URI = "extra_image_uri"

        fun createIntent(context: Context, imageUri: String): Intent {
            return Intent(context, ProcessingActivity::class.java)
                .putExtra(EXTRA_IMAGE_URI, imageUri)
        }
    }
}
