package com.example.myapplication.ui.scan

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import com.example.myapplication.R
import com.example.myapplication.databinding.FragmentScanBinding
import com.example.myapplication.ui.main.MainTabController
import com.example.myapplication.ui.processing.ProcessingActivity
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import java.io.File
import java.nio.ByteBuffer
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import kotlin.math.abs

class ScanFragment : Fragment() {

    private var _binding: FragmentScanBinding? = null
    private val binding get() = _binding!!

    private var cameraProvider: ProcessCameraProvider? = null
    private var camera: Camera? = null
    private var imageCapture: ImageCapture? = null
    private lateinit var cameraExecutor: ExecutorService

    private var flashEnabled = false
    private var stableFrameCount = 0
    private var lastLuma: Double? = null
    private var currentGuidance = GuidanceState.PERMISSION

    private val galleryLauncher = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let { startProcessing(it.toString(), fromGallery = true) }
    }

    private val permissionLauncher = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            showPermissionUi(false)
            startCamera()
        } else {
            showPermissionUi(true)
            applyGuidance(GuidanceState.PERMISSION)
        }
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentScanBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        cameraExecutor = Executors.newSingleThreadExecutor()

        bindActions()
        handleBackPress()
        updateFlashUi()
        ensureCameraAccess()
        applyGuidance(GuidanceState.DETECTING)
    }

    override fun onDestroyView() {
        cameraProvider?.unbindAll()
        if (::cameraExecutor.isInitialized) {
            cameraExecutor.shutdown()
        }
        super.onDestroyView()
        _binding = null
    }

    private fun bindActions() {
        binding.btnBack.setOnClickListener {
            (activity as? MainTabController)?.openTab(R.id.navHome)
        }
        binding.btnRecent.setOnClickListener {
            (activity as? MainTabController)?.openTab(R.id.navBills)
        }
        binding.btnGallery.setOnClickListener {
            galleryLauncher.launch("image/*")
        }
        binding.btnHelp.setOnClickListener {
            showTipsDialog()
        }
        binding.btnGrantPermission.setOnClickListener {
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
        binding.btnFlash.setOnClickListener {
            flashEnabled = !flashEnabled
            camera?.cameraControl?.enableTorch(flashEnabled)
            updateFlashUi()
        }
        binding.btnCapture.setOnClickListener {
            capturePhoto()
        }
    }

    private fun handleBackPress() {
        requireActivity().onBackPressedDispatcher.addCallback(viewLifecycleOwner, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                (activity as? MainTabController)?.openTab(R.id.navHome)
            }
        })
    }

    private fun ensureCameraAccess() {
        when {
            ContextCompat.checkSelfPermission(requireContext(), Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED -> {
                showPermissionUi(false)
                startCamera()
            }
            shouldShowRequestPermissionRationale(Manifest.permission.CAMERA) -> {
                showPermissionUi(true)
                applyGuidance(GuidanceState.PERMISSION)
            }
            else -> permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(requireContext())
        cameraProviderFuture.addListener(
            {
                cameraProvider = cameraProviderFuture.get()
                bindCameraUseCases()
            },
            ContextCompat.getMainExecutor(requireContext())
        )
    }

    private fun bindCameraUseCases() {
        val provider = cameraProvider ?: return

        val preview = Preview.Builder().build().also {
            it.setSurfaceProvider(binding.previewView.surfaceProvider)
        }

        imageCapture = ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
            .build()

        val analysis = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()
            .also { useCase ->
                useCase.setAnalyzer(cameraExecutor, ::analyzeFrame)
            }

        val selector = CameraSelector.DEFAULT_BACK_CAMERA

        runCatching {
            provider.unbindAll()
            camera = provider.bindToLifecycle(
                viewLifecycleOwner,
                selector,
                preview,
                imageCapture,
                analysis
            )
            if (flashEnabled) {
                camera?.cameraControl?.enableTorch(true)
            }
        }.onFailure {
            showPermissionUi(true)
            applyGuidance(GuidanceState.PERMISSION)
        }
    }

    private fun analyzeFrame(imageProxy: ImageProxy) {
        val luma = imageProxy.planes.firstOrNull()?.buffer?.averageLuma() ?: 0.0
        val movement = lastLuma?.let { abs(it - luma) } ?: 0.0
        lastLuma = luma

        val nextState = when {
            luma < 52 -> {
                stableFrameCount = 0
                GuidanceState.LOW_LIGHT
            }
            movement > 14 -> {
                stableFrameCount = (stableFrameCount - 2).coerceAtLeast(0)
                GuidanceState.HOLD_STEADY
            }
            stableFrameCount < 10 -> {
                stableFrameCount++
                GuidanceState.DETECTING
            }
            else -> {
                stableFrameCount = (stableFrameCount + 1).coerceAtMost(20)
                GuidanceState.READY
            }
        }

        if (nextState != currentGuidance && view != null) {
            binding.root.post {
                if (view != null) {
                    applyGuidance(nextState)
                }
            }
        }
        imageProxy.close()
    }

    private fun capturePhoto() {
        val capture = imageCapture ?: return
        binding.btnCapture.isEnabled = false
        animateCaptureButton()
        applyGuidance(GuidanceState.CAPTURED)

        val photoFile = File.createTempFile("bill_camera_", ".jpg", requireContext().cacheDir)
        val outputOptions = ImageCapture.OutputFileOptions.Builder(photoFile).build()

        capture.takePicture(
            outputOptions,
            ContextCompat.getMainExecutor(requireContext()),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                    val savedUri = outputFileResults.savedUri ?: Uri.fromFile(photoFile)
                    startProcessing(savedUri.toString(), fromGallery = false)
                }

                override fun onError(exception: ImageCaptureException) {
                    binding.btnCapture.isEnabled = true
                    applyGuidance(GuidanceState.DETECTING)
                }
            }
        )
    }

    private fun startProcessing(imageUri: String, fromGallery: Boolean) {
        if (fromGallery) {
            applyGuidance(GuidanceState.CAPTURED)
        }
        binding.btnCapture.isEnabled = false
        binding.viewFlash.alpha = if (fromGallery) 0f else 0.92f
        binding.viewFlash.animate()
            .alpha(0f)
            .setDuration(240L)
            .withEndAction {
                startActivity(ProcessingActivity.createIntent(requireContext(), imageUri))
                requireActivity().overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out)
                binding.btnCapture.isEnabled = true
                applyGuidance(GuidanceState.DETECTING)
            }
            .start()
    }

    private fun animateCaptureButton() {
        binding.btnCapture.animate().cancel()
        binding.btnCapture.animate()
            .scaleX(0.93f)
            .scaleY(0.93f)
            .setDuration(90L)
            .withEndAction {
                binding.btnCapture.animate()
                    .scaleX(1f)
                    .scaleY(1f)
                    .setDuration(150L)
                    .start()
            }
            .start()
    }

    private fun updateFlashUi() {
        binding.btnFlash.text = if (flashEnabled) getString(R.string.scan_flash_on) else getString(R.string.scan_flash)
        binding.btnFlash.setTextColor(
            if (flashEnabled) {
                ContextCompat.getColor(requireContext(), R.color.accent_mint)
            } else {
                ContextCompat.getColor(requireContext(), R.color.text_main)
            }
        )
    }

    private fun showPermissionUi(visible: Boolean) {
        binding.cardPermission.isVisible = visible
        binding.btnCapture.isEnabled = !visible
        binding.btnFlash.isEnabled = !visible
        binding.previewView.alpha = if (visible) 0.25f else 1f
    }

    private fun showTipsDialog() {
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(getString(R.string.scan_help_title))
            .setMessage(getString(R.string.scan_help_body))
            .setPositiveButton(getString(R.string.scan_help_cta), null)
            .show()
    }

    private fun applyGuidance(state: GuidanceState) {
        if (!this::cameraExecutor.isInitialized && state != GuidanceState.PERMISSION) return
        if (currentGuidance == state && binding.tvStatus.text.isNotBlank()) return

        currentGuidance = state
        binding.cardStatus.animate().alpha(0f).setDuration(120L).withEndAction {
            binding.tvStatus.text = getString(state.statusRes)
            binding.cardStatus.setCardBackgroundColor(state.containerColor(requireContext()))
            binding.viewStatusDot.background.setTint(state.dotColor(requireContext()))
            binding.cardStatus.alpha = 1f
        }.start()

        binding.tvGuide.animate().alpha(0f).setDuration(120L).withEndAction {
            binding.tvGuide.text = getString(state.titleRes)
            binding.tvGuide.alpha = 1f
        }.start()

        binding.tvGuideSub.animate().alpha(0f).setDuration(120L).withEndAction {
            binding.tvGuideSub.text = getString(state.subtitleRes)
            binding.tvGuideSub.alpha = 1f
        }.start()

        binding.scanOverlay.setVisualState(state.visualState)
    }

    private fun ByteBuffer.averageLuma(): Double {
        rewind()
        var sum = 0L
        while (hasRemaining()) {
            sum += get().toInt() and 0xFF
        }
        rewind()
        return if (limit() == 0) 0.0 else sum.toDouble() / limit().toDouble()
    }

    private enum class GuidanceState(
        val statusRes: Int,
        val titleRes: Int,
        val subtitleRes: Int,
        val visualState: ScanVisualState
    ) {
        DETECTING(
            statusRes = R.string.scan_status_detecting,
            titleRes = R.string.scan_hint_default,
            subtitleRes = R.string.scan_hint_sub_default,
            visualState = ScanVisualState.DETECTING
        ),
        HOLD_STEADY(
            statusRes = R.string.scan_status_hold,
            titleRes = R.string.scan_hint_hold,
            subtitleRes = R.string.scan_hint_sub_hold,
            visualState = ScanVisualState.DETECTING
        ),
        READY(
            statusRes = R.string.scan_status_ready,
            titleRes = R.string.scan_hint_ready,
            subtitleRes = R.string.scan_hint_sub_ready,
            visualState = ScanVisualState.READY
        ),
        LOW_LIGHT(
            statusRes = R.string.scan_status_light,
            titleRes = R.string.scan_hint_light,
            subtitleRes = R.string.scan_hint_sub_light,
            visualState = ScanVisualState.WARNING
        ),
        CAPTURED(
            statusRes = R.string.scan_status_captured,
            titleRes = R.string.scan_hint_captured,
            subtitleRes = R.string.scan_hint_sub_captured,
            visualState = ScanVisualState.CAPTURED
        ),
        PERMISSION(
            statusRes = R.string.scan_status_permission,
            titleRes = R.string.scan_hint_permission,
            subtitleRes = R.string.scan_hint_sub_permission,
            visualState = ScanVisualState.WARNING
        );

        fun containerColor(context: android.content.Context): Int {
            return when (this) {
                READY -> Color.parseColor("#E8FFFA")
                LOW_LIGHT, PERMISSION -> Color.parseColor("#FFF4D6")
                CAPTURED -> Color.parseColor("#EAF2FF")
                DETECTING, HOLD_STEADY -> Color.parseColor("#EAF4FF")
            }
        }

        fun dotColor(context: android.content.Context): Int {
            return when (this) {
                READY -> ContextCompat.getColor(context, R.color.accent_mint)
                LOW_LIGHT, PERMISSION -> ContextCompat.getColor(context, R.color.warning_text)
                CAPTURED -> ContextCompat.getColor(context, R.color.accent_sky)
                DETECTING, HOLD_STEADY -> ContextCompat.getColor(context, R.color.accent_sky)
            }
        }
    }
}
