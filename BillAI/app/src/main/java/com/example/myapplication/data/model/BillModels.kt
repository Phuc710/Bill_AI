package com.example.myapplication.data.model

import com.google.gson.annotations.SerializedName

data class BillResponse(
    val bill_id: String,
    val status: String, // "completed" | "failed"
    val failed_step: String?,
    val message: String?,
    val original_image_url: String?,
    val cropped_image_url: String?,
    val data: BillData?,
    val items: List<BillItem>?,
    val meta: BillMeta?
)

data class BillData(
    val store_name: String?,
    val address: String?,
    val phone: String?,
    val invoice_id: String?,
    val datetime: String?,
    val total: Long,
    val subtotal: Long?,
    val cash_given: Long?,
    val cash_change: Long?,
    val payment_method: String?,
    val currency: String?
)

data class BillItem(
    val name: String,
    val quantity: Int,
    val unit_price: Long,
    val total_price: Long
)

data class BillMeta(
    val needs_review: Boolean,
    val detect_confidence: Double,
    val processing_ms: Double,
    val gemini_error: String?
)

data class ListBillsResponse(
    val data: List<BillSummary>,
    val page: Int,
    val limit: Int
)

data class BillSummary(
    val id: String,
    val user_id: String,
    val status: String,
    val store_name: String?,
    val total: Long?,
    val currency: String?,
    val payment_method: String?,
    val cropped_image_url: String?,
    val needs_review: Boolean,
    val created_at: String,
    val failed_step: String?
)
