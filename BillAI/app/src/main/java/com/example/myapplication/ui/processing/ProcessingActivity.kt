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
import com.example.myapplication.data.repository.AuthRepository
import com.example.myapplication.data.repository.BillRepository
import com.example.myapplication.databinding.ActivityProcessingBinding
import com.example.myapplication.ui.result.ResultActivity
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
        Glide.with(this)
            .load(imageUri)
            .centerCrop()
            .into(binding.ivCapturedPreview)
    }

    private fun playEntranceAnimation() {
        binding.viewProcessingScrim.animate()
            .alpha(0.64f)
            .setDuration(280L)
            .start()

        binding.cardProcessing.animate()
            .translationY(0f)
            .alpha(1f)
            .setDuration(320L)
            .start()
    }

    private fun uploadBill(imageUri: Uri) {
        lifecycleScope.launch {
            val userId = authRepository.getUserId()
            if (userId.isNullOrBlank()) {
                Toast.makeText(this@ProcessingActivity, getString(R.string.processing_error_session), Toast.LENGTH_SHORT).show()
                finish()
                return@launch
            }

            progressJob = launchPipelineSteps()
            val imageFile = copyUriToTempFile(imageUri)

            billRepository.extractBill(imageFile, userId).fold(
                onSuccess = { result ->
                    progressJob?.cancel()
                    animateStep(
                        index = 5,
                        total = 5,
                        progress = 100,
                        title = getString(R.string.processing_done_title),
                        hint = getString(R.string.processing_done_hint)
                    )
                    delay(220L)
                    startActivity(ResultActivity.createIntent(this@ProcessingActivity, result.bill_id))
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

    private fun launchPipelineSteps(): Job {
        val steps = listOf(
            PipelineStep(1, 5, 14, getString(R.string.processing_step_upload_title), getString(R.string.processing_step_upload_hint)),
            PipelineStep(2, 5, 34, getString(R.string.processing_step_detect_title), getString(R.string.processing_step_detect_hint)),
            PipelineStep(3, 5, 58, getString(R.string.processing_step_ocr_title), getString(R.string.processing_step_ocr_hint)),
            PipelineStep(4, 5, 82, getString(R.string.processing_step_normalize_title), getString(R.string.processing_step_normalize_hint)),
            PipelineStep(5, 5, 96, getString(R.string.processing_step_wait_title), getString(R.string.processing_step_wait_hint))
        )

        return lifecycleScope.launch {
            for (step in steps) {
                animateStep(
                    index = step.index,
                    total = step.total,
                    progress = step.progress,
                    title = step.title,
                    hint = step.hint
                )
                delay(850L)
            }
        }
    }

    private fun animateStep(
        index: Int,
        total: Int,
        progress: Int,
        title: String,
        hint: String
    ) {
        binding.progressIndicator.progress = progress
        binding.tvStepIndex.text = getString(R.string.processing_step_format, index, total)

        binding.tvCurrentStep.animate()
            .alpha(0f)
            .setDuration(120L)
            .withEndAction {
                binding.tvCurrentStep.text = title
                binding.tvCurrentStep.alpha = 1f
            }
            .start()

        binding.tvStepHint.animate()
            .alpha(0f)
            .setDuration(120L)
            .withEndAction {
                binding.tvStepHint.text = hint
                binding.tvStepHint.alpha = 1f
            }
            .start()
    }

    private fun copyUriToTempFile(uri: Uri): File {
        val tempFile = File.createTempFile("bill_upload_", ".jpg", cacheDir)
        val inputStream = if (uri.scheme == "file") {
            FileInputStream(File(requireNotNull(uri.path)))
        } else {
            contentResolver.openInputStream(uri)
        }

        inputStream?.use { input ->
            FileOutputStream(tempFile).use { output ->
                input.copyTo(output)
            }
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

    private data class PipelineStep(
        val index: Int,
        val total: Int,
        val progress: Int,
        val title: String,
        val hint: String
    )
}
