package com.example.myapplication.ui.profile

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.example.myapplication.data.repository.AuthRepository
import com.example.myapplication.data.repository.BillRepository
import com.example.myapplication.databinding.FragmentProfileBinding
import com.example.myapplication.ui.auth.LoginActivity
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.util.Locale

/**
 * ProfileFragment — thông tin tài khoản, thống kê, đăng xuất.
 */
class ProfileFragment : Fragment() {

    private var _binding: FragmentProfileBinding? = null
    private val binding get() = _binding!!

    private val authRepo = AuthRepository()
    private val billRepo = BillRepository()

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentProfileBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        loadUserInfo()

        binding.btnLogout.setOnClickListener {
            lifecycleScope.launch {
                authRepo.logout()
                // Navigate back to Login, clear backstack
                val intent = Intent(requireContext(), LoginActivity::class.java)
                intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
                startActivity(intent)
            }
        }
    }

    private fun loadUserInfo() {
        lifecycleScope.launch {
            val email = authRepo.getUserEmail() ?: "Không rõ"
            val userId = authRepo.getUserId() ?: return@launch

            binding.tvUserEmail.text = email

            // Load bill stats
            billRepo.listBills(userId, page = 1, limit = 100).fold(
                onSuccess = { response ->
                    val bills = response.data
                    val total = bills.sumOf { it.total ?: 0L }
                    binding.tvTotalBills.text = bills.size.toString()
                    binding.tvTotalAmount.text = formatCurrency(total)
                },
                onFailure = {
                    binding.tvTotalBills.text = "—"
                    binding.tvTotalAmount.text = "—"
                }
            )
        }
    }

    private fun formatCurrency(amount: Long): String {
        return NumberFormat.getNumberInstance(Locale("vi", "VN")).format(amount) + "đ"
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
