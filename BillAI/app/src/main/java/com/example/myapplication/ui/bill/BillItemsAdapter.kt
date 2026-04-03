package com.example.myapplication.ui.bill

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.example.myapplication.data.model.BillItem
import com.example.myapplication.databinding.ItemBillItemBinding
import java.text.NumberFormat
import java.util.Locale

/**
 * BillItemsAdapter — danh sách các món trong hóa đơn.
 * Mỗi row: tên món, số lượng, đơn giá, thành tiền.
 */
class BillItemsAdapter : ListAdapter<BillItem, BillItemsAdapter.ItemViewHolder>(DiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ItemViewHolder {
        val binding = ItemBillItemBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ItemViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ItemViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class ItemViewHolder(private val binding: ItemBillItemBinding) :
        RecyclerView.ViewHolder(binding.root) {

        fun bind(item: BillItem) {
            binding.tvItemName.text = item.name
            binding.tvItemQty.text = "x${item.quantity}"
            binding.tvItemUnitPrice.text = formatCurrency(item.unit_price)
            binding.tvItemTotal.text = formatCurrency(item.total_price)
        }

        private fun formatCurrency(amount: Long): String {
            return NumberFormat.getNumberInstance(Locale.forLanguageTag("vi-VN")).format(amount) + "đ"
        }
    }

    class DiffCallback : DiffUtil.ItemCallback<BillItem>() {
        override fun areItemsTheSame(old: BillItem, new: BillItem) = old.name == new.name
        override fun areContentsTheSame(old: BillItem, new: BillItem) = old == new
    }
}
