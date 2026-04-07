package com.example.myapplication.ui.home

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.bumptech.glide.Glide
import com.example.myapplication.R
import com.example.myapplication.data.bootstrap.AppBootstrapCoordinator
import com.example.myapplication.data.bootstrap.AppSessionSnapshot
import com.example.myapplication.data.bootstrap.AppSessionStore
import com.example.myapplication.data.model.BillSummary
import com.example.myapplication.databinding.FragmentHomeBinding
import com.example.myapplication.ui.bills.BillDetailActivity
import com.example.myapplication.ui.bills.BillsAdapter
import com.example.myapplication.ui.main.MainTabController
import com.example.myapplication.util.toCurrencyText
import kotlinx.coroutines.launch
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.temporal.ChronoUnit
import java.util.Locale

class HomeFragment : Fragment() {

    enum class TimeFilter { ALL, WEEK, MONTH }

    private var _binding: FragmentHomeBinding? = null
    private val binding get() = _binding!!

    private val bootstrapCoordinator by lazy {
        AppBootstrapCoordinator(requireContext().applicationContext)
    }
    private lateinit var recentBillsAdapter: BillsAdapter

    private var allBills: List<BillSummary> = emptyList()
    private var currentFilter = TimeFilter.ALL

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
        setupQuickActions()
    }

    override fun onResume() {
        super.onResume()
        loadDashboard()
    }

    private fun setupRecentBills() {
        recentBillsAdapter = BillsAdapter(showStatusChip = false) { bill ->
            startActivity(BillDetailActivity.createIntent(requireContext(), bill.id))
        }
        binding.rvRecentBills.layoutManager = LinearLayoutManager(requireContext())
        binding.rvRecentBills.adapter = recentBillsAdapter
    }

    private fun setupQuickActions() {
        val navigateToBills = {
            (activity as? MainTabController)?.openTab(R.id.navBills)
        }

        binding.cardSearchBar.setOnClickListener { navigateToBills() }
        binding.btnViewAllRecent.setOnClickListener { navigateToBills() }
        binding.btnHeaderProfile.setOnClickListener {
            (activity as? MainTabController)?.openTab(R.id.navProfile)
        }

        binding.chipAll.setOnClickListener {
            currentFilter = TimeFilter.ALL
            updateStats()
        }
        binding.chipWeek.setOnClickListener {
            currentFilter = TimeFilter.WEEK
            updateStats()
        }
        binding.chipMonth.setOnClickListener {
            currentFilter = TimeFilter.MONTH
            updateStats()
        }
    }

    private fun loadDashboard() {
        lifecycleScope.launch {
            AppSessionStore.currentSnapshot()?.let(::renderSnapshot)
            binding.progressBar.isVisible = AppSessionStore.currentSnapshot() == null

            bootstrapCoordinator.ensureSession().fold(
                onSuccess = { snapshot ->
                    binding.progressBar.isVisible = false
                    renderSnapshot(snapshot)
                },
                onFailure = {
                    binding.progressBar.isVisible = false
                    allBills = emptyList()
                    renderFallbackHeader()
                    updateStats()
                }
            )
        }
    }

    private fun renderSnapshot(snapshot: AppSessionSnapshot) {
        val displayName = snapshot.user.displayName.ifBlank { "Bill AI" }
        binding.tvGreeting.text = getString(R.string.home_default_greeting)
        binding.tvGreetingName.text = displayName

        val avatarUrl = snapshot.user.avatarUrl
        if (!avatarUrl.isNullOrBlank()) {
            Glide.with(this)
                .load(avatarUrl)
                .circleCrop()
                .into(binding.ivAvatar)
            binding.ivAvatar.isVisible = true
            binding.tvAvatarInitial.isVisible = false
        } else {
            binding.tvAvatarInitial.text = displayName.firstOrNull()?.uppercase() ?: "B"
            binding.ivAvatar.isVisible = false
            binding.tvAvatarInitial.isVisible = true
        }

        allBills = snapshot.bills
        updateStats()
    }

    private fun renderFallbackHeader() {
        binding.tvGreeting.text = getString(R.string.home_default_greeting)
        binding.tvGreetingName.text = "Bill AI"
        binding.ivAvatar.isVisible = false
        binding.tvAvatarInitial.isVisible = true
        binding.tvAvatarInitial.text = "B"
    }

    @SuppressLint("NewApi")
    private fun updateStats() {
        val zone = ZoneId.systemDefault()
        val now = ZonedDateTime.now(zone)

        val filteredBills = (if (currentFilter == TimeFilter.ALL) {
            allBills
        } else {
            allBills.filter { bill ->
                parseBillDate(bill.created_at, zone)?.let { billDate ->
                    when (currentFilter) {
                        TimeFilter.WEEK -> !billDate.isAfter(now) &&
                            ChronoUnit.DAYS.between(billDate.toLocalDate(), now.toLocalDate()) <= 7
                        TimeFilter.MONTH -> billDate.monthValue == now.monthValue && billDate.year == now.year
                        TimeFilter.ALL -> true
                    }
                } ?: false
            }
        }).sortedByDescending { bill ->
            parseBillDate(bill.created_at, zone)?.toInstant()?.toEpochMilli() ?: Long.MIN_VALUE
        }

        if (filteredBills.isEmpty()) {
            binding.tvValSpend.text = 0L.toCurrencyText()
            binding.tvValCount.text = formatCount(0)
            binding.tvValAverage.text = 0L.toCurrencyText()
            binding.tvValTopCategory.text = "N/A"
            recentBillsAdapter.submitList(emptyList())
            binding.layoutEmptyState.isVisible = true
            binding.rvRecentBills.isVisible = false
            return
        }

        val spend = filteredBills.sumOf { it.total ?: 0L }
        val count = filteredBills.size
        val average = if (count > 0) spend / count else 0L

        val categoryMap = filteredBills
            .filter { !it.category.isNullOrBlank() }
            .groupBy { it.category!! }
            .mapValues { entry -> entry.value.sumOf { it.total ?: 0L } }

        val topCategoryEntry = categoryMap.maxByOrNull { it.value }
        val topCategoryText = if (topCategoryEntry != null && spend > 0) {
            val pct = (topCategoryEntry.value * 100 / spend).toInt()
            "${topCategoryEntry.key} - $pct%"
        } else {
            "N/A"
        }

        binding.tvValSpend.text = spend.toCurrencyText()
        binding.tvValCount.text = formatCount(count)
        binding.tvValAverage.text = average.toCurrencyText()
        binding.tvValTopCategory.text = topCategoryText

        recentBillsAdapter.submitList(filteredBills.take(5))
        binding.layoutEmptyState.isVisible = false
        binding.rvRecentBills.isVisible = true
    }

    private fun formatCount(value: Int): String = String.format(Locale.getDefault(), "%d", value)

    @SuppressLint("NewApi")
    private fun parseBillDate(value: String, zone: ZoneId): ZonedDateTime? {
        return runCatching {
            OffsetDateTime.parse(value).atZoneSameInstant(zone)
        }.recoverCatching {
            LocalDateTime.parse(value).atZone(zone)
        }.getOrNull()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
