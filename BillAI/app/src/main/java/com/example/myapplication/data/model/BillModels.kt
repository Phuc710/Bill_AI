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
    @SerializedName("store_address") val address: String?,
    @SerializedName("store_phone") val phone: String?,
    @SerializedName("invoice_number") val invoice_id: String?,
    @SerializedName("issued_at") val datetime: String?,
    @SerializedName("total_amount") val total: Long,
    val subtotal: Long?,
    @SerializedName("cash_tendered") val cash_given: Long?,
    val cash_change: Long?,
    val payment_method: String?,
    val category: String?,
    val currency: String?
)

data class BillItem(
    @SerializedName("item_name") val name: String,
    val quantity: Int,
    val unit_price: Long,
    val total_price: Long
)

data class BillMeta(
    val needs_review: Boolean,
    val detect_confidence: Double,
    val processing_ms: Double,
    val llm_error: String?
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
    val failed_step: String?,
    val store_name: String?,
    val invoice_number: String?,
    val issued_at: String?,
    @SerializedName("total_amount") val total: Long?,
    val currency: String?,
    val category: String?,
    val payment_method: String?,   // not in v_invoice_summary view → null (ok)
    val cropped_image_url: String?,
    val needs_review: Boolean,
    val processing_time_ms: Double?,
    val created_at: String,
    val item_count: Int?
)
