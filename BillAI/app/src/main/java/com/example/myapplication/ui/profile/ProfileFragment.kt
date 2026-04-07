package com.example.myapplication.ui.profile

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.example.myapplication.R
import com.example.myapplication.data.bootstrap.AppBootstrapCoordinator
import com.example.myapplication.data.bootstrap.AppSessionSnapshot
import com.example.myapplication.data.bootstrap.AppSessionStore
import com.example.myapplication.data.repository.AuthRepository
import com.example.myapplication.databinding.FragmentProfileBinding
import com.example.myapplication.ui.splash.SplashActivity
import com.example.myapplication.util.toCurrencyText
import kotlinx.coroutines.launch
import java.util.Locale

class ProfileFragment : Fragment() {

    private var _binding: FragmentProfileBinding? = null
    private val binding get() = _binding!!

    private val authRepository = AuthRepository()
    private val bootstrapCoordinator by lazy {
        AppBootstrapCoordinator(requireContext().applicationContext)
    }

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
                AppSessionStore.clear()
                startActivity(
                    Intent(requireContext(), SplashActivity::class.java).apply {
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
                    }
                )
            }
        }
    }

    private fun loadProfile() {
        lifecycleScope.launch {
            AppSessionStore.currentSnapshot()?.let(::renderSnapshot)

            bootstrapCoordinator.ensureSession().fold(
                onSuccess = ::renderSnapshot,
                onFailure = {
                    binding.tvUserEmail.text = getString(R.string.profile_email_empty)
                    binding.tvTotalBills.text = formatCount(0)
                    binding.tvTotalAmount.text = 0L.toCurrencyText()
                    binding.tvSyncStatus.text = getString(R.string.profile_sync_failed)
                    binding.tvReviewInfo.text = getString(R.string.profile_retry_later)
                }
            )
        }
    }

    private fun renderSnapshot(snapshot: AppSessionSnapshot) {
        val reviewCount = snapshot.bills.count {
            it.needs_review || it.status.equals("failed", ignoreCase = true)
        }

        binding.tvUserEmail.text = snapshot.user.email.ifBlank {
            getString(R.string.profile_email_empty)
        }
        binding.tvTotalBills.text = formatCount(snapshot.bills.size)
        binding.tvTotalAmount.text = snapshot.bills.sumOf { it.total ?: 0L }.toCurrencyText()
        binding.tvSyncStatus.text = getString(
            if (snapshot.syncSucceeded) R.string.profile_sync_ok else R.string.profile_sync_failed
        )
        binding.tvReviewInfo.text = if (reviewCount > 0) {
            getString(R.string.profile_review_count, reviewCount)
        } else {
            getString(R.string.profile_review_default)
        }
    }

    private fun formatCount(value: Int): String = String.format(Locale.getDefault(), "%d", value)

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
