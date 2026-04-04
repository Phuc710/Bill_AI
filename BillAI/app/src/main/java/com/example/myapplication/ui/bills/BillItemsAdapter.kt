package com.example.myapplication.ui.bills

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.example.myapplication.R
import com.example.myapplication.data.model.BillItem
import com.example.myapplication.databinding.ItemBillItemBinding
import com.example.myapplication.util.toCurrencyText

class BillItemsAdapter : ListAdapter<BillItem, BillItemsAdapter.ItemViewHolder>(DiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ItemViewHolder {
        val binding = ItemBillItemBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ItemViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ItemViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class ItemViewHolder(
        private val binding: ItemBillItemBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: BillItem) {
            binding.tvItemName.text = item.name
            binding.tvItemQty.text = binding.root.context.getString(R.string.bill_item_qty_format, item.quantity)
            binding.tvItemUnitPrice.text = item.unit_price.toCurrencyText()
            binding.tvItemTotal.text = item.total_price.toCurrencyText()
        }
    }

    class DiffCallback : DiffUtil.ItemCallback<BillItem>() {
        override fun areItemsTheSame(oldItem: BillItem, newItem: BillItem): Boolean = oldItem.name == newItem.name
        override fun areContentsTheSame(oldItem: BillItem, newItem: BillItem): Boolean = oldItem == newItem
    }
}
