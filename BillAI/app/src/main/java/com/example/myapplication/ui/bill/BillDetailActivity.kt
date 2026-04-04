package com.example.myapplication.ui.bill

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.bumptech.glide.Glide
import com.example.myapplication.R
import com.example.myapplication.data.model.BillResponse
import com.example.myapplication.data.repository.BillRepository
import com.example.myapplication.databinding.ActivityBillDetailBinding
import com.example.myapplication.util.toCurrencyText
import com.example.myapplication.util.toDisplayDateTime
import kotlinx.coroutines.launch

class BillDetailActivity : AppCompatActivity() {

    private lateinit var binding: ActivityBillDetailBinding
    private val billRepository = BillRepository()
    private lateinit var itemsAdapter: BillItemsAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        binding = ActivityBillDetailBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val billId = intent.getStringExtra(EXTRA_BILL_ID) ?: run {
            finish()
            return
        }

        itemsAdapter = BillItemsAdapter()
        binding.rvItems.layoutManager = LinearLayoutManager(this)
        binding.rvItems.adapter = itemsAdapter

        binding.btnBack.setOnClickListener { finish() }
        binding.btnDelete.setOnClickListener { confirmDelete(billId) }
        binding.btnShare.setOnClickListener { shareBill() }

        loadBillDetail(billId)
    }

    private fun loadBillDetail(billId: String) {
        lifecycleScope.launch {
            binding.progressDetail.isVisible = true
            billRepository.getBillDetail(billId).fold(
                onSuccess = {
                    binding.progressDetail.isVisible = false
                    renderBill(it)
                },
                onFailure = {
                    binding.progressDetail.isVisible = false
                    Toast.makeText(this@BillDetailActivity, getString(R.string.detail_load_failed), Toast.LENGTH_SHORT).show()
                    finish()
                }
            )
        }
    }

    private fun renderBill(bill: BillResponse) {
        binding.tvNeedsReview.isVisible = bill.meta?.needs_review == true || bill.status.equals("failed", true)
        binding.tvNeedsReview.text = bill.message ?: getString(R.string.detail_review_fallback)

        Glide.with(this)
            .load(bill.cropped_image_url ?: bill.original_image_url)
            .centerCrop()
            .into(binding.ivCroppedImage)

        binding.tvStoreName.text = bill.data?.store_name ?: getString(R.string.detail_store_fallback)
        binding.tvAddress.text = bill.data?.address ?: getString(R.string.detail_address_empty)
        binding.tvPhone.text = bill.data?.phone ?: getString(R.string.detail_phone_empty)
        binding.tvDatetime.text = bill.data?.datetime.toDisplayDateTime()
        binding.tvInvoiceId.text = bill.data?.invoice_id ?: getString(R.string.detail_invoice_empty)
        binding.tvPayment.text = bill.data?.payment_method ?: getString(R.string.detail_unknown)
        binding.tvSubtotal.text = bill.data?.subtotal.toCurrencyText()
        binding.tvTotal.text = bill.data?.total.toCurrencyText()
        binding.tvCashGiven.text = bill.data?.cash_given.toCurrencyText()
        binding.tvCashChange.text = bill.data?.cash_change.toCurrencyText()
        binding.tvMeta.text = getString(R.string.detail_status_format, bill.status)

        itemsAdapter.submitList(bill.items.orEmpty())
    }

    private fun shareBill() {
        val summary = listOf(
            binding.tvStoreName.text.toString(),
            binding.tvDatetime.text.toString(),
            binding.tvTotal.text.toString()
        ).joinToString("\n")

        startActivity(
            Intent.createChooser(
                Intent(Intent.ACTION_SEND).apply {
                    type = "text/plain"
                    putExtra(Intent.EXTRA_TEXT, summary)
                },
                getString(R.string.detail_share_title)
            )
        )
    }

    private fun confirmDelete(billId: String) {
        AlertDialog.Builder(this)
            .setTitle(R.string.detail_delete_title)
            .setMessage(R.string.detail_delete_message)
            .setPositiveButton(R.string.detail_delete_confirm) { _, _ ->
                lifecycleScope.launch {
                    billRepository.deleteBill(billId).fold(
                        onSuccess = { finish() },
                        onFailure = {
                            Toast.makeText(this@BillDetailActivity, getString(R.string.detail_delete_failed), Toast.LENGTH_SHORT).show()
                        }
                    )
                }
            }
            .setNegativeButton(R.string.detail_delete_cancel, null)
            .show()
    }

    companion object {
        const val EXTRA_BILL_ID = "extra_bill_id"
    }
}
