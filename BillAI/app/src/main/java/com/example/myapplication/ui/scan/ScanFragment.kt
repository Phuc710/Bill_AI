package com.example.myapplication.ui.scan

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.MediaStore
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.FileProvider
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.example.myapplication.data.repository.AuthRepository
import com.example.myapplication.data.repository.BillRepository
import com.example.myapplication.databinding.FragmentScanBinding
import com.example.myapplication.ui.bill.BillDetailActivity
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileOutputStream

/**
 * ScanFragment — chọn ảnh từ gallery hoặc chụp ảnh → upload lên backend.
 * Hiển thị overlay progress khi đang xử lý, chuyển sang BillDetailActivity khi done.
 */
class ScanFragment : Fragment() {

    private var _binding: FragmentScanBinding? = null
    private val binding get() = _binding!!

    private val billRepo = BillRepository()
    private val authRepo = AuthRepository()

    private var selectedImageFile: File? = null
    private var cameraPhotoUri: Uri? = null

    // ActivityResult launchers
    private val galleryLauncher = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let { handleSelectedImage(it) }
    }

    private val cameraLauncher = registerForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        if (success) cameraPhotoUri?.let { handleSelectedImage(it) }
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentScanBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        binding.btnPickGallery.setOnClickListener {
            galleryLauncher.launch("image/*")
        }

        binding.btnCamera.setOnClickListener {
            openCamera()
        }

        binding.btnUpload.setOnClickListener {
            uploadBill()
        }
    }

    private fun openCamera() {
        val photoFile = File.createTempFile("bill_", ".jpg", requireContext().cacheDir)
        cameraPhotoUri = FileProvider.getUriForFile(
            requireContext(),
            "${requireContext().packageName}.provider",
            photoFile
        )
        cameraLauncher.launch(cameraPhotoUri!!)
    }

    private fun handleSelectedImage(uri: Uri) {
        // Show preview
        binding.ivPreview.setImageURI(uri)
        binding.tvHint.visibility = View.GONE
        binding.btnUpload.visibility = View.VISIBLE

        // Copy to a real File for Retrofit upload
        val tmpFile = File.createTempFile("upload_", ".jpg", requireContext().cacheDir)
        requireContext().contentResolver.openInputStream(uri)?.use { input ->
            FileOutputStream(tmpFile).use { output -> input.copyTo(output) }
        }
        selectedImageFile = tmpFile
    }

    private fun uploadBill() {
        val imageFile = selectedImageFile ?: return
        setProcessing(true, "Đang gửi ảnh lên server...")

        lifecycleScope.launch {
            val userId = authRepo.getUserId() ?: ""

            billRepo.extractBill(imageFile, userId).fold(
                onSuccess = { result ->
                    setProcessing(false)
                    // Navigate to detail regardless of complete/failed
                    val intent = Intent(requireContext(), BillDetailActivity::class.java)
                    intent.putExtra(BillDetailActivity.EXTRA_BILL_ID, result.bill_id)
                    startActivity(intent)
                    resetScan()
                },
                onFailure = { e ->
                    setProcessing(false)
                    Toast.makeText(requireContext(), "Lỗi: ${e.message}", Toast.LENGTH_LONG).show()
                }
            )
        }
    }

    private fun setProcessing(active: Boolean, step: String = "") {
        binding.layoutProcessing.visibility = if (active) View.VISIBLE else View.GONE
        binding.tvProcessingStep.text = step
        binding.btnUpload.isEnabled = !active
        binding.btnPickGallery.isEnabled = !active
        binding.btnCamera.isEnabled = !active
    }

    private fun resetScan() {
        selectedImageFile = null
        binding.ivPreview.setImageDrawable(null)
        binding.tvHint.visibility = View.VISIBLE
        binding.btnUpload.visibility = View.GONE
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
