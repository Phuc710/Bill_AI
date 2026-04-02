package com.example.myapplication.ui.history

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.myapplication.data.model.BillSummary
import com.example.myapplication.data.repository.AuthRepository
import com.example.myapplication.data.repository.BillRepository
import com.example.myapplication.databinding.FragmentHistoryBinding
import com.example.myapplication.ui.bill.BillDetailActivity
import kotlinx.coroutines.launch

/**
 * HistoryFragment — hiển thị toàn bộ danh sách hóa đơn của user.
 * Click vào item → mở BillDetailActivity.
 */
class HistoryFragment : Fragment() {

    private var _binding: FragmentHistoryBinding? = null
    private val binding get() = _binding!!

    private val billRepo = BillRepository()
    private val authRepo = AuthRepository()
    private lateinit var adapter: BillsAdapter

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentHistoryBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupRecyclerView()
    }

    override fun onResume() {
        super.onResume()
        loadBills()
    }

    private fun setupRecyclerView() {
        adapter = BillsAdapter { bill ->
            // Click → open detail
            val intent = Intent(requireContext(), BillDetailActivity::class.java)
            intent.putExtra(BillDetailActivity.EXTRA_BILL_ID, bill.id)
            startActivity(intent)
        }
        binding.rvBills.layoutManager = LinearLayoutManager(requireContext())
        binding.rvBills.adapter = adapter
    }

    private fun loadBills() {
        lifecycleScope.launch {
            val userId = authRepo.getUserId() ?: return@launch
            binding.progressLoading.visibility = View.VISIBLE
            binding.tvEmpty.visibility = View.GONE

            billRepo.listBills(userId, page = 1).fold(
                onSuccess = { response ->
                    binding.progressLoading.visibility = View.GONE
                    val bills = response.data
                    if (bills.isEmpty()) {
                        binding.tvEmpty.visibility = View.VISIBLE
                    } else {
                        adapter.submitList(bills)
                    }
                },
                onFailure = {
                    binding.progressLoading.visibility = View.GONE
                    binding.tvEmpty.text = "Lỗi tải dữ liệu"
                    binding.tvEmpty.visibility = View.VISIBLE
                }
            )
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null // Prevent memory leak
    }
}
