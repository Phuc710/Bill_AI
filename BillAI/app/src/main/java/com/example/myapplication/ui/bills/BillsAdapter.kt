package com.example.myapplication.ui.bills

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
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
            binding.tvStoreName.text = bill.store_name?.ifBlank { context.getString(R.string.history_store_fallback) }
                ?: context.getString(R.string.history_store_fallback)
            binding.tvDate.text = bill.created_at.toDisplayDate()
            binding.tvTotal.text = bill.total.toCurrencyText()
            binding.tvMeta.text = listOfNotNull(
                bill.payment_method?.takeIf(String::isNotBlank),
                bill.item_count?.let { context.getString(R.string.history_item_count, it) }
            ).joinToString(" • ").ifBlank { context.getString(R.string.history_meta_saved) }

            val showStatus = bill.needs_review || bill.status.equals("failed", ignoreCase = true)
            binding.tvStatus.visibility = if (showStatus) View.VISIBLE else View.GONE
            binding.tvStatus.text = bill.statusLabel()

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
    }

    class BillDiffCallback : DiffUtil.ItemCallback<BillSummary>() {
        override fun areItemsTheSame(oldItem: BillSummary, newItem: BillSummary): Boolean = oldItem.id == newItem.id
        override fun areContentsTheSame(oldItem: BillSummary, newItem: BillSummary): Boolean = oldItem == newItem
    }
}
