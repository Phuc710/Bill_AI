package com.example.myapplication.ui.history

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.bumptech.glide.Glide
import com.example.myapplication.R
import com.example.myapplication.data.model.BillSummary
import com.example.myapplication.databinding.ItemBillBinding
import java.text.NumberFormat
import java.util.Locale

/**
 * BillsAdapter — RecyclerView adapter dùng DiffUtil để tối ưu rendering.
 * Mỗi row = 1 BillSummary → hiển thị: thumbnail, store name, date, total.
 */
class BillsAdapter(
    private val onClick: (BillSummary) -> Unit
) : ListAdapter<BillSummary, BillsAdapter.BillViewHolder>(BillDiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): BillViewHolder {
        val binding = ItemBillBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return BillViewHolder(binding)
    }

    override fun onBindViewHolder(holder: BillViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class BillViewHolder(private val binding: ItemBillBinding) :
        RecyclerView.ViewHolder(binding.root) {

        fun bind(bill: BillSummary) {
            // Store name — fallback if null
            binding.tvStoreName.text = bill.store_name?.ifBlank { "Hóa đơn" } ?: "Hóa đơn"

            // Date — format từ ISO string
            binding.tvDate.text = formatDate(bill.created_at)

            // Total — format VND
            binding.tvTotal.text = formatCurrency(bill.total ?: 0)

            // Needs review badge
            if (bill.needs_review || bill.status == "failed") {
                binding.tvStatus.visibility = ViewGroup.VISIBLE
                binding.tvStatus.text = if (bill.failed_step != null) "⚠ Xử lý thất bại" else "⚠ Cần kiểm tra"
            } else {
                binding.tvStatus.visibility = ViewGroup.GONE
            }

            // Thumbnail from Supabase Storage URL
            if (!bill.cropped_image_url.isNullOrBlank()) {
                Glide.with(binding.ivCroppedThumb)
                    .load(bill.cropped_image_url)
                    .placeholder(R.drawable.ic_logo)
                    .centerCrop()
                    .into(binding.ivCroppedThumb)
            } else {
                binding.ivCroppedThumb.setImageResource(R.drawable.ic_logo)
            }

            binding.root.setOnClickListener { onClick(bill) }
        }

        private fun formatDate(isoDate: String): String {
            return try {
                val parts = isoDate.substringBefore("T").split("-")
                "${parts[2]}/${parts[1]}/${parts[0]}"
            } catch (e: Exception) {
                isoDate
            }
        }

        private fun formatCurrency(amount: Long): String {
            return NumberFormat.getNumberInstance(Locale("vi", "VN")).format(amount) + "đ"
        }
    }

    class BillDiffCallback : DiffUtil.ItemCallback<BillSummary>() {
        override fun areItemsTheSame(old: BillSummary, new: BillSummary) = old.id == new.id
        override fun areContentsTheSame(old: BillSummary, new: BillSummary) = old == new
    }
}
