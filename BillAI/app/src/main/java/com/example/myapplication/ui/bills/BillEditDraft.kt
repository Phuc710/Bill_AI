package com.example.myapplication.ui.bills

import com.example.myapplication.data.model.BillResponse
import com.example.myapplication.util.toBackendDateTime

data class BillEditDraft(
    val storeName: String,
    val address: String,
    val phone: String,
    val invoiceId: String,
    val paymentMethod: String,
    val totalAmount: Long?,
    val dateTime: String,
    val category: String,
    val note: String
) {
    fun toPayload(): Map<String, Any?> {
        return mutableMapOf<String, Any?>().apply {
            put("store_name", storeName)
            put("store_address", address.ifBlank { null })
            put("store_phone", phone.ifBlank { null })
            put("invoice_number", invoiceId.ifBlank { null })
            put("payment_method", paymentMethod.ifBlank { null })
            totalAmount?.let { put("total_amount", it) }
            dateTime.toBackendDateTime()?.let { put("issued_at", it) }
            put("category", category.ifBlank { "Khác" })
            put("summary", note.ifBlank { null })
            put("failed_step", null)
            put("status", "completed")
            put("needs_review", false)
        }
    }

    companion object {
        fun fromBill(bill: BillResponse): BillEditDraft {
            return BillEditDraft(
                storeName = bill.data?.store_name.orEmpty(),
                address = bill.data?.address.orEmpty(),
                phone = bill.data?.phone.orEmpty(),
                invoiceId = bill.data?.invoice_id.orEmpty(),
                paymentMethod = bill.data?.payment_method.orEmpty(),
                totalAmount = bill.data?.total,
                dateTime = bill.data?.datetime.orEmpty(),
                category = bill.data?.category.orEmpty(),
                note = bill.message.orEmpty()
            )
        }
    }
}
