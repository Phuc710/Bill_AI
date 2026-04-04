package com.example.myapplication.ui.home

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.myapplication.R
import com.example.myapplication.data.repository.AuthRepository
import com.example.myapplication.data.repository.BillRepository
import com.example.myapplication.databinding.FragmentHomeBinding
import com.example.myapplication.ui.bill.BillDetailActivity
import com.example.myapplication.ui.bills.BillsAdapter
import com.example.myapplication.util.matchesMonth
import com.example.myapplication.util.toCurrencyText
import kotlinx.coroutines.launch
import java.time.YearMonth

class HomeFragment : Fragment() {

    private var _binding: FragmentHomeBinding? = null
    private val binding get() = _binding!!

    private val authRepository = AuthRepository()
    private val billRepository = BillRepository()
    private lateinit var recentBillsAdapter: BillsAdapter

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentHomeBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupRecentBills()
    }

    override fun onResume() {
        super.onResume()
        loadDashboard()
    }

    private fun setupRecentBills() {
        recentBillsAdapter = BillsAdapter { bill ->
            startActivity(
                Intent(requireContext(), BillDetailActivity::class.java)
                    .putExtra(BillDetailActivity.EXTRA_BILL_ID, bill.id)
            )
        }
        binding.rvRecentBills.layoutManager = LinearLayoutManager(requireContext())
        binding.rvRecentBills.adapter = recentBillsAdapter
    }

    private fun loadDashboard() {
        lifecycleScope.launch {
            val email = authRepository.getUserEmail().orEmpty()
            val fallbackText = getString(R.string.profile_email_empty)
            val displayName = authRepository.getUserDisplayName().orEmpty().ifBlank {
                email.substringBefore("@").ifBlank { email.ifBlank { fallbackText } }
            }
            binding.tvGreeting.text = getString(R.string.home_default_greeting)
            binding.tvGreetingName.text = displayName

            val userId = authRepository.getUserId() ?: return@launch
            binding.progressBar.isVisible = true

            billRepository.listBills(userId, page = 1, limit = 100).fold(
                onSuccess = { response ->
                    binding.progressBar.isVisible = false
                    val bills = response.data
                    val currentMonth = YearMonth.now()
                    val monthlyBills = bills.filter { it.matchesMonth(currentMonth) }
                    val monthlyTotal = monthlyBills.sumOf { it.total ?: 0L }
                    val reviewCount = bills.count { it.needs_review || it.status.equals("failed", true) }

                    binding.tvMonthSpend.text = monthlyTotal.toCurrencyText()
                    binding.tvMonthBills.text = monthlyBills.size.toString()
                    binding.tvReviewCount.text = reviewCount.toString()
                    binding.tvTotalBills.text = bills.size.toString()

                    val recentBills = bills.take(3)
                    recentBillsAdapter.submitList(recentBills)
                    binding.layoutEmptyState.isVisible = recentBills.isEmpty()
                    binding.rvRecentBills.isVisible = recentBills.isNotEmpty()
                },
                onFailure = {
                    binding.progressBar.isVisible = false
                    binding.layoutEmptyState.isVisible = true
                    binding.rvRecentBills.isVisible = false
                }
            )
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
