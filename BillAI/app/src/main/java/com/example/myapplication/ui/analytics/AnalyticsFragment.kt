package com.example.myapplication.ui.analytics

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.example.myapplication.R
import com.example.myapplication.data.bootstrap.AppBootstrapCoordinator
import com.example.myapplication.data.bootstrap.AppSessionSnapshot
import com.example.myapplication.data.bootstrap.AppSessionStore
import com.example.myapplication.data.model.BillSummary
import com.example.myapplication.databinding.FragmentAnalyticsBinding
import com.example.myapplication.util.matchesMonth
import com.example.myapplication.util.toCurrencyText
import kotlinx.coroutines.launch
import java.time.YearMonth
import java.util.Locale

class AnalyticsFragment : Fragment() {

    private var _binding: FragmentAnalyticsBinding? = null
    private val binding get() = _binding!!

    private val bootstrapCoordinator by lazy {
        AppBootstrapCoordinator(requireContext().applicationContext)
    }

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
            AppSessionStore.currentSnapshot()?.let(::renderSnapshot)
            binding.progressAnalytics.isVisible = AppSessionStore.currentSnapshot() == null

            bootstrapCoordinator.ensureSession().fold(
                onSuccess = { snapshot ->
                    binding.progressAnalytics.isVisible = false
                    renderSnapshot(snapshot)
                },
                onFailure = {
                    binding.progressAnalytics.isVisible = false
                    renderAnalytics(emptyList())
                }
            )
        }
    }

    private fun renderSnapshot(snapshot: AppSessionSnapshot) {
        renderAnalytics(snapshot.bills)
    }

    private fun renderAnalytics(bills: List<BillSummary>) {
        val monthBills = bills.filter { it.matchesMonth(YearMonth.now()) }
        val totalSpend = monthBills.sumOf { it.total ?: 0L }
        val avgSpend = if (monthBills.isEmpty()) 0L else totalSpend / monthBills.size
        val reviewCount = bills.count {
            it.needs_review || it.status.equals("failed", ignoreCase = true)
        }
        val topStore = bills
            .groupingBy { it.store_name?.takeIf(String::isNotBlank) ?: getString(R.string.analytics_store_unknown) }
            .eachCount()
            .maxByOrNull { it.value }

        binding.tvMonthlySpend.text = totalSpend.toCurrencyText()
        binding.tvAverageSpend.text = avgSpend.toCurrencyText()
        binding.tvScanCount.text = String.format(Locale.getDefault(), "%d", bills.size)
        binding.tvReviewCount.text = String.format(Locale.getDefault(), "%d", reviewCount)
        binding.tvTopStore.text = topStore?.key ?: getString(R.string.analytics_no_data)
        binding.tvTopStoreMeta.text = topStore?.value?.let {
            getString(R.string.analytics_store_count, it)
        } ?: getString(R.string.analytics_top_store_default)
        binding.tvFailedCount.text = String.format(
            Locale.getDefault(),
            "%d",
            bills.count { it.status.equals("failed", ignoreCase = true) }
        )
        binding.layoutAnalyticsEmpty.isVisible = bills.isEmpty()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
