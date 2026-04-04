package com.example.myapplication.ui.result

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.bumptech.glide.Glide
import com.example.myapplication.R
import com.example.myapplication.data.model.BillResponse
import com.example.myapplication.data.repository.BillRepository
import com.example.myapplication.databinding.ActivityResultBinding
import com.example.myapplication.ui.bill.BillDetailActivity
import com.example.myapplication.ui.bill.BillItemsAdapter
import com.example.myapplication.util.toCurrencyText
import com.example.myapplication.util.toDisplayDateTime
import com.example.myapplication.util.toProcessingTimeText
import kotlinx.coroutines.launch

class ResultActivity : AppCompatActivity() {

    private lateinit var binding: ActivityResultBinding
    private val billRepository = BillRepository()
    private lateinit var itemsAdapter: BillItemsAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        binding = ActivityResultBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val billId = intent.getStringExtra(EXTRA_BILL_ID) ?: run {
            finish()
            return
        }

        itemsAdapter = BillItemsAdapter()
        binding.rvItems.layoutManager = LinearLayoutManager(this)
        binding.rvItems.adapter = itemsAdapter

        binding.btnClose.setOnClickListener { finish() }
        binding.btnOpenDetail.setOnClickListener {
            startActivity(
                Intent(this, BillDetailActivity::class.java)
                    .putExtra(BillDetailActivity.EXTRA_BILL_ID, billId)
            )
            finish()
        }

        loadResult(billId)
    }

    private fun loadResult(billId: String) {
        lifecycleScope.launch {
            billRepository.getBillDetail(billId).fold(
                onSuccess = ::renderResult,
                onFailure = {
                    binding.progressResult.isVisible = false
                    binding.layoutError.isVisible = true
                }
            )
        }
    }

    private fun renderResult(bill: BillResponse) {
        binding.progressResult.isVisible = false
        binding.contentGroup.visibility = View.VISIBLE

        binding.tvStatus.text = if (bill.status.equals("completed", true)) {
            getString(R.string.result_status_done)
        } else {
            getString(R.string.result_status_review)
        }
        binding.tvStatusMeta.text = bill.meta?.processing_ms.toProcessingTimeText()

        Glide.with(this)
            .load(bill.cropped_image_url ?: bill.original_image_url)
            .centerCrop()
            .into(binding.ivBill)

        binding.tvStoreName.text = bill.data?.store_name ?: getString(R.string.result_store_unknown)
        binding.tvDateTime.text = bill.data?.datetime.toDisplayDateTime()
        binding.tvTotal.text = bill.data?.total.toCurrencyText()
        binding.tvPayment.text = bill.data?.payment_method ?: getString(R.string.result_unknown)
        binding.tvReviewBanner.isVisible = bill.meta?.needs_review == true || bill.status.equals("failed", true)
        binding.tvReviewBanner.text = bill.message ?: getString(R.string.result_review_fallback)

        itemsAdapter.submitList(bill.items.orEmpty())
    }

    companion object {
        private const val EXTRA_BILL_ID = "extra_bill_id"

        fun createIntent(context: Context, billId: String): Intent {
            return Intent(context, ResultActivity::class.java)
                .putExtra(EXTRA_BILL_ID, billId)
        }
    }
}
