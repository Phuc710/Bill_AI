package com.example.myapplication.ui.bills

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.view.isVisible
import androidx.core.widget.doAfterTextChanged
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.myapplication.R
import com.example.myapplication.data.bootstrap.AppBootstrapCoordinator
import com.example.myapplication.data.bootstrap.AppSessionSnapshot
import com.example.myapplication.data.bootstrap.AppSessionStore
import com.example.myapplication.data.model.BillSummary
import com.example.myapplication.databinding.FragmentBillsBinding
import com.example.myapplication.util.matchesSearchQuery
import kotlinx.coroutines.launch

class BillsFragment : Fragment() {

    private var _binding: FragmentBillsBinding? = null
    private val binding get() = _binding!!

    private val bootstrapCoordinator by lazy {
        AppBootstrapCoordinator(requireContext().applicationContext)
    }
    private lateinit var billsAdapter: BillsAdapter

    private var allBills: List<BillSummary> = emptyList()
    private var selectedFilter: BillFilter = BillFilter.ALL

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentBillsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupRecyclerView()
        setupSearchAndFilters()
    }

    override fun onResume() {
        super.onResume()
        loadBills()
    }

    private fun setupRecyclerView() {
        billsAdapter = BillsAdapter { bill ->
            startActivity(BillDetailActivity.createIntent(requireContext(), bill.id))
        }
        binding.rvBills.layoutManager = LinearLayoutManager(requireContext())
        binding.rvBills.adapter = billsAdapter
    }

    private fun setupSearchAndFilters() {
        binding.inputSearch.doAfterTextChanged { applyFilters() }

        binding.chipAll.setOnClickListener {
            selectedFilter = BillFilter.ALL
            applyFilters()
        }
        binding.chipCompleted.setOnClickListener {
            selectedFilter = BillFilter.COMPLETED
            applyFilters()
        }
        binding.chipReview.setOnClickListener {
            selectedFilter = BillFilter.REVIEW
            applyFilters()
        }
    }

    private fun loadBills() {
        lifecycleScope.launch {
            AppSessionStore.currentSnapshot()?.let(::renderSnapshot)
            binding.progressLoading.isVisible = AppSessionStore.currentSnapshot() == null

            bootstrapCoordinator.ensureSession().fold(
                onSuccess = { snapshot ->
                    binding.progressLoading.isVisible = false
                    renderSnapshot(snapshot)
                },
                onFailure = {
                    binding.progressLoading.isVisible = false
                    allBills = emptyList()
                    applyFilters()
                }
            )
        }
    }

    private fun renderSnapshot(snapshot: AppSessionSnapshot) {
        allBills = snapshot.bills
        applyFilters()
    }

    private fun applyFilters() {
        val query = binding.inputSearch.text?.toString().orEmpty().trim()
        val filtered = allBills.filter { bill ->
            val matchesFilter = when (selectedFilter) {
                BillFilter.ALL -> true
                BillFilter.COMPLETED -> bill.status.equals("completed", ignoreCase = true)
                BillFilter.REVIEW -> bill.needs_review || bill.status.equals("failed", ignoreCase = true)
            }
            bill.matchesSearchQuery(query) && matchesFilter
        }

        billsAdapter.submitList(filtered)
        binding.layoutEmptyState.isVisible = filtered.isEmpty()
        binding.rvBills.isVisible = filtered.isNotEmpty()
        binding.tvResults.text = getString(R.string.bills_result_count, filtered.size)

        val hasAnyBills = allBills.isNotEmpty()
        binding.tvEmptyTitle.text = if (hasAnyBills) {
            getString(R.string.bills_empty_filtered_title)
        } else {
            getString(R.string.bills_empty_title)
        }
        binding.tvEmptySubtitle.text = if (hasAnyBills) {
            getString(R.string.bills_empty_filtered_subtitle)
        } else {
            getString(R.string.bills_empty_subtitle)
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    private enum class BillFilter {
        ALL,
        COMPLETED,
        REVIEW
    }
}
