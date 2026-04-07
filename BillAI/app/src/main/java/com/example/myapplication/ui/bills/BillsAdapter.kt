package com.example.myapplication.ui.bills

import android.graphics.Color
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.view.isVisible
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.bumptech.glide.Glide
import com.example.myapplication.R
import com.example.myapplication.data.model.BillSummary
import com.example.myapplication.databinding.ItemBillBinding
import com.example.myapplication.util.statusLabel
import com.example.myapplication.util.toCurrencyText
import com.example.myapplication.util.toDisplayDate

class BillsAdapter(
    private val showStatusChip: Boolean = true,
    private val onClick: (BillSummary) -> Unit
) : ListAdapter<BillSummary, BillsAdapter.BillViewHolder>(BillDiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): BillViewHolder {
        val binding = ItemBillBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return BillViewHolder(binding)
    }

    override fun onBindViewHolder(holder: BillViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class BillViewHolder(
        private val binding: ItemBillBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(bill: BillSummary) {
            val context = binding.root.context

            binding.tvStoreName.text = bill.store_name?.ifBlank { null }
                ?: context.getString(R.string.history_store_fallback)
            binding.tvDate.text = bill.created_at.toDisplayDate()

            val category = bill.category?.ifBlank { null } ?: "Khác"
            binding.tvCategory.text = category

            val itemText = bill.item_count
                ?.takeIf { it > 0 }
                ?.let { context.getString(R.string.history_item_count, it) }
                ?: context.getString(R.string.home_recent_items_unknown)
            val paymentText = bill.payment_method?.ifBlank { null }
                ?: context.getString(R.string.home_recent_payment_unknown)
            binding.tvMeta.text = context.getString(R.string.home_recent_meta_format, itemText, paymentText)

            binding.tvTotal.text = bill.total.toCurrencyText()

            val isFailed = bill.status.equals("failed", ignoreCase = true)
            val showStatus = showStatusChip && isFailed

            binding.cardStatus.isVisible = showStatus
            if (showStatus) {
                binding.tvStatus.text = context.getString(R.string.analytics_failed)
                binding.tvStatus.setTextColor(Color.parseColor("#DC2626"))
                binding.cardStatus.setCardBackgroundColor(Color.parseColor("#FEF2F2"))
            }

            if (!bill.cropped_image_url.isNullOrBlank()) {
                Glide.with(binding.ivCroppedThumb)
                    .load(bill.cropped_image_url)
                    .placeholder(R.color.divider)
                    .centerCrop()
                    .into(binding.ivCroppedThumb)
            } else {
                binding.ivCroppedThumb.setBackgroundColor(Color.parseColor("#F1F5F9"))
                binding.ivCroppedThumb.setImageResource(R.drawable.ic_logo)
            }

            binding.root.setOnClickListener { onClick(bill) }
        }
    }

    class BillDiffCallback : DiffUtil.ItemCallback<BillSummary>() {
        override fun areItemsTheSame(oldItem: BillSummary, newItem: BillSummary): Boolean = oldItem.id == newItem.id
        override fun areContentsTheSame(oldItem: BillSummary, newItem: BillSummary): Boolean = oldItem == newItem
    }
}
