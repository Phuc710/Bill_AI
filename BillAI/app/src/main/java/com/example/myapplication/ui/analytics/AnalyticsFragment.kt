package com.example.myapplication.ui.analytics

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.example.myapplication.R
import com.example.myapplication.data.model.BillSummary
import com.example.myapplication.data.repository.AuthRepository
import com.example.myapplication.data.repository.BillRepository
import com.example.myapplication.databinding.FragmentAnalyticsBinding
import com.example.myapplication.util.matchesMonth
import com.example.myapplication.util.toCurrencyText
import kotlinx.coroutines.launch
import java.time.YearMonth

class AnalyticsFragment : Fragment() {

    private var _binding: FragmentAnalyticsBinding? = null
    private val binding get() = _binding!!

    private val authRepository = AuthRepository()
    private val billRepository = BillRepository()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentAnalyticsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onResume() {
        super.onResume()
        loadAnalytics()
    }

    private fun loadAnalytics() {
        lifecycleScope.launch {
            val userId = authRepository.getUserId() ?: return@launch
            binding.progressAnalytics.isVisible = true

            billRepository.listBills(userId, page = 1, limit = 100).fold(
                onSuccess = { response ->
                    binding.progressAnalytics.isVisible = false
                    renderAnalytics(response.data)
                },
                onFailure = {
                    binding.progressAnalytics.isVisible = false
                    renderAnalytics(emptyList())
                }
            )
        }
    }

    private fun renderAnalytics(bills: List<BillSummary>) {
        val monthBills = bills.filter { it.matchesMonth(YearMonth.now()) }
        val totalSpend = monthBills.sumOf { it.total ?: 0L }
        val avgSpend = if (monthBills.isEmpty()) 0L else totalSpend / monthBills.size
        val failedCount = bills.count { it.status.equals("failed", ignoreCase = true) }
        val reviewCount = bills.count { it.needs_review }
        val topStore = bills
            .groupingBy { it.store_name?.takeIf(String::isNotBlank) ?: getString(R.string.analytics_store_unknown) }
            .eachCount()
            .maxByOrNull { it.value }

        binding.tvMonthlySpend.text = totalSpend.toCurrencyText()
        binding.tvAverageSpend.text = avgSpend.toCurrencyText()
        binding.tvScanCount.text = bills.size.toString()
        binding.tvReviewCount.text = reviewCount.toString()
        binding.tvFailedCount.text = failedCount.toString()
        binding.tvTopStore.text = topStore?.key ?: getString(R.string.analytics_no_data)
        binding.tvTopStoreMeta.text = topStore?.value?.let {
            getString(R.string.analytics_store_count, it)
        } ?: getString(R.string.analytics_top_store_default)
        binding.layoutAnalyticsEmpty.isVisible = bills.isEmpty()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
