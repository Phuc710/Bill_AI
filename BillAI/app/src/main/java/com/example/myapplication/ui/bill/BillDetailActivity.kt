package com.example.myapplication.ui.bill

import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.bumptech.glide.Glide
import com.example.myapplication.data.model.BillItem
import com.example.myapplication.data.model.BillResponse
import com.example.myapplication.data.repository.BillRepository
import com.example.myapplication.databinding.ActivityBillDetailBinding
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.util.Locale

/**
 * BillDetailActivity — hiển thị chi tiết 1 hóa đơn.
 * Nhận bill_id qua Intent extra, gọi API lấy full data.
 * Hiển thị: ảnh crop, thông tin cửa hàng, danh sách món, tổng tiền.
 */
class BillDetailActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_BILL_ID = "extra_bill_id"
    }

    private lateinit var binding: ActivityBillDetailBinding
    private val billRepo = BillRepository()
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

        setupUI()
        loadBillDetail(billId)
    }

    private fun setupUI() {
        binding.btnBack.setOnClickListener { finish() }

        itemsAdapter = BillItemsAdapter()
        binding.rvItems.layoutManager = LinearLayoutManager(this)
        binding.rvItems.adapter = itemsAdapter
    }

    private fun loadBillDetail(billId: String) {
        lifecycleScope.launch {
            billRepo.getBillDetail(billId).fold(
                onSuccess = { bill -> renderBill(bill) },
                onFailure = {
                    Toast.makeText(this@BillDetailActivity, "Không thể tải hóa đơn", Toast.LENGTH_SHORT).show()
                    finish()
                }
            )
        }
    }

    private fun renderBill(bill: BillResponse) {
        val data = bill.data

        // Cropped image
        if (!bill.cropped_image_url.isNullOrBlank()) {
            Glide.with(this).load(bill.cropped_image_url).centerCrop().into(binding.ivCroppedImage)
        }

        // Needs review warning
        if (bill.meta?.needs_review == true || bill.status == "failed") {
            binding.tvNeedsReview.visibility = View.VISIBLE
        }

        // Store info
        binding.tvStoreName.text = data?.store_name ?: "Không rõ cửa hàng"
        binding.tvAddress.text = data?.address ?: ""
        binding.tvPhone.text = data?.phone ?: ""
        binding.tvAddress.visibility = if (data?.address.isNullOrBlank()) View.GONE else View.VISIBLE
        binding.tvPhone.visibility = if (data?.phone.isNullOrBlank()) View.GONE else View.VISIBLE

        // Date & Invoice ID
        binding.tvDatetime.text = formatDate(data?.datetime ?: "")
        binding.tvInvoiceId.text = data?.invoice_id ?: "—"

        // Items
        itemsAdapter.submitList(bill.items ?: emptyList())

        // Totals
        binding.tvTotal.text = formatCurrency(data?.total ?: 0)
        binding.tvCashGiven.text = data?.cash_given?.let { formatCurrency(it) } ?: "—"
        binding.tvCashChange.text = data?.cash_change?.let { formatCurrency(it) } ?: "—"
        binding.tvPayment.text = data?.payment_method ?: "—"

        // Delete button
        binding.btnDelete.setOnClickListener {
            confirmDelete(bill.bill_id)
        }
    }

    private fun confirmDelete(billId: String) {
        AlertDialog.Builder(this)
            .setTitle("Xóa hóa đơn")
            .setMessage("Bạn có chắc muốn xóa hóa đơn này?")
            .setPositiveButton("Xóa") { _, _ ->
                lifecycleScope.launch {
                    billRepo.deleteBill(billId).fold(
                        onSuccess = { finish() },
                        onFailure = { Toast.makeText(this@BillDetailActivity, "Xóa thất bại", Toast.LENGTH_SHORT).show() }
                    )
                }
            }
            .setNegativeButton("Hủy", null)
            .show()
    }

    private fun formatDate(isoDate: String): String {
        return try {
            val parts = isoDate.substringBefore("T").split("-")
            "${parts[2]}/${parts[1]}/${parts[0]}"
        } catch (e: Exception) { isoDate }
    }

    private fun formatCurrency(amount: Long): String {
        return NumberFormat.getNumberInstance(Locale("vi", "VN")).format(amount) + "đ"
    }
}
