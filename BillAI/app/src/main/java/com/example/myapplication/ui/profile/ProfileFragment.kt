package com.example.myapplication.ui.profile

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.example.myapplication.R
import com.example.myapplication.data.repository.AuthRepository
import com.example.myapplication.data.repository.BillRepository
import com.example.myapplication.databinding.FragmentProfileBinding
import com.example.myapplication.ui.auth.LoginActivity
import com.example.myapplication.util.toCurrencyText
import kotlinx.coroutines.launch

class ProfileFragment : Fragment() {

    private var _binding: FragmentProfileBinding? = null
    private val binding get() = _binding!!

    private val authRepository = AuthRepository()
    private val billRepository = BillRepository()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentProfileBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onResume() {
        super.onResume()
        loadProfile()
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        binding.btnLogout.setOnClickListener {
            lifecycleScope.launch {
                authRepository.logout()
                startActivity(
                    Intent(requireContext(), LoginActivity::class.java).apply {
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
                    }
                )
            }
        }
    }

    private fun loadProfile() {
        lifecycleScope.launch {
            binding.tvUserEmail.text = authRepository.getUserEmail() ?: getString(R.string.profile_email_empty)

            val userId = authRepository.getUserId() ?: return@launch
            billRepository.listBills(userId, page = 1, limit = 100).fold(
                onSuccess = { response ->
                    val bills = response.data
                    binding.tvTotalBills.text = bills.size.toString()
                    binding.tvTotalAmount.text = bills.sumOf { it.total ?: 0L }.toCurrencyText()
                    binding.tvSyncStatus.text = getString(R.string.profile_sync_ok)
                    binding.tvReviewInfo.text = getString(R.string.profile_review_count, bills.count { it.needs_review })
                },
                onFailure = {
                    binding.tvTotalBills.text = "0"
                    binding.tvTotalAmount.text = 0L.toCurrencyText()
                    binding.tvSyncStatus.text = getString(R.string.profile_sync_failed)
                    binding.tvReviewInfo.text = getString(R.string.profile_retry_later)
                }
            )
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
