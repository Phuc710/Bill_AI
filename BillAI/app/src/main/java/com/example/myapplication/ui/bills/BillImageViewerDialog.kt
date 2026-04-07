package com.example.myapplication.ui.bills

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.view.isVisible
import androidx.fragment.app.DialogFragment
import com.bumptech.glide.Glide
import com.example.myapplication.databinding.DialogBillImageViewerBinding

class BillImageViewerDialog : DialogFragment() {

    private var _binding: DialogBillImageViewerBinding? = null
    private val binding get() = _binding!!

    private var currentMode: BillImageMode = BillImageMode.CROPPED

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setStyle(STYLE_NORMAL, android.R.style.Theme_Black_NoTitleBar_Fullscreen)
        currentMode = arguments?.getString(ARG_INITIAL_MODE)
            ?.let(BillImageMode::valueOf)
            ?: BillImageMode.CROPPED
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = DialogBillImageViewerBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val croppedUrl = arguments?.getString(ARG_CROPPED_URL)
        val originalUrl = arguments?.getString(ARG_ORIGINAL_URL)
        val canToggle = !croppedUrl.isNullOrBlank() &&
            !originalUrl.isNullOrBlank() &&
            croppedUrl != originalUrl

        binding.groupImageModes.isVisible = canToggle
        binding.btnClose.setOnClickListener { dismiss() }
        binding.btnModeCropped.setOnClickListener {
            currentMode = BillImageMode.CROPPED
            renderImage(croppedUrl, originalUrl)
        }
        binding.btnModeOriginal.setOnClickListener {
            currentMode = BillImageMode.ORIGINAL
            renderImage(croppedUrl, originalUrl)
        }

        if (!canToggle) {
            currentMode = if (!croppedUrl.isNullOrBlank()) BillImageMode.CROPPED else BillImageMode.ORIGINAL
        }

        renderImage(croppedUrl, originalUrl)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    private fun renderImage(croppedUrl: String?, originalUrl: String?) {
        val targetUrl = when (currentMode) {
            BillImageMode.CROPPED -> croppedUrl ?: originalUrl
            BillImageMode.ORIGINAL -> originalUrl ?: croppedUrl
        }

        binding.btnModeCropped.isChecked = currentMode == BillImageMode.CROPPED
        binding.btnModeOriginal.isChecked = currentMode == BillImageMode.ORIGINAL

        Glide.with(this)
            .load(targetUrl)
            .into(binding.ivPreview)
    }

    companion object {
        private const val ARG_CROPPED_URL = "arg_cropped_url"
        private const val ARG_ORIGINAL_URL = "arg_original_url"
        private const val ARG_INITIAL_MODE = "arg_initial_mode"
        private const val TAG = "BillImageViewerDialog"

        fun show(
            host: androidx.fragment.app.FragmentManager,
            croppedUrl: String?,
            originalUrl: String?,
            initialMode: BillImageMode
        ) {
            BillImageViewerDialog().apply {
                arguments = Bundle().apply {
                    putString(ARG_CROPPED_URL, croppedUrl)
                    putString(ARG_ORIGINAL_URL, originalUrl)
                    putString(ARG_INITIAL_MODE, initialMode.name)
                }
            }.show(host, TAG)
        }
    }
}
