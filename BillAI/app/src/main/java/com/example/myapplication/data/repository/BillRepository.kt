package com.example.myapplication.data.repository

import com.example.myapplication.BuildConfig
import com.example.myapplication.data.api.RetrofitClient
import com.example.myapplication.data.api.SupabaseManager
import com.example.myapplication.data.model.BillResponse
import com.example.myapplication.data.model.ListBillsResponse
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File

class BillRepository {

    private val api = RetrofitClient.apiService
    private val supabaseApi = RetrofitClient.supabaseApiService

    private val supabaseUrl = BuildConfig.SUPABASE_URL
    private val supabaseKey = BuildConfig.SUPABASE_ANON_KEY

    suspend fun extractBill(imageFile: File, userId: String): Result<BillResponse> {
        return try {
            val requestFile = imageFile.asRequestBody("image/*".toMediaTypeOrNull())
            val imagePart = MultipartBody.Part.createFormData("image", imageFile.name, requestFile)
            val userIdPart = userId.toRequestBody("text/plain".toMediaTypeOrNull())

            val response = api.extractBill(imagePart, userIdPart)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Upload Failed: ${response.errorBody()?.string()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun listBills(userId: String, page: Int = 1, limit: Int = 20): Result<ListBillsResponse> {
        return try {
            val token = SupabaseManager.auth.currentAccessTokenOrNull() ?: supabaseKey
            val url = "$supabaseUrl/rest/v1/v_invoice_summary"
            val response = supabaseApi.listBills(url, supabaseKey, "Bearer $token", "eq.$userId")
            if (response.isSuccessful && response.body() != null) {
                Result.success(ListBillsResponse(response.body()!!, page, limit))
            } else {
                Result.failure(Exception("Supabase Network Error: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    @Suppress("UNCHECKED_CAST")
    suspend fun getBillDetail(billId: String): Result<BillResponse> {
        return try {
            val token = SupabaseManager.auth.currentAccessTokenOrNull() ?: supabaseKey
            val url = "$supabaseUrl/rest/v1/invoices"
            val response = supabaseApi.getBillDetails(url, supabaseKey, "Bearer $token", "eq.$billId")
            
            if (response.isSuccessful && response.body() != null) {
                val list = response.body()!!
                if (list.isEmpty()) return Result.failure(Exception("Bill not found"))
                val row = list[0]
                
                // Map nested items
                val rawItems = row["items"] as? List<Map<String, Any>> ?: emptyList()
                val parsedItems = rawItems.map {
                    com.example.myapplication.data.model.BillItem(
                        name = it["item_name"] as? String ?: "",
                        quantity = (it["quantity"] as? Number)?.toInt() ?: 1,
                        unit_price = (it["unit_price"] as? Number)?.toLong() ?: 0L,
                        total_price = (it["total_price"] as? Number)?.toLong() ?: 0L
                    )
                }

                // Map row to BillResponse format
                val billData = com.example.myapplication.data.model.BillData(
                    store_name = row["store_name"] as? String,
                    address = row["store_address"] as? String,
                    phone = row["store_phone"] as? String,
                    invoice_id = row["invoice_number"] as? String,
                    datetime = row["issued_at"] as? String,
                    total = (row["total_amount"] as? Number)?.toLong() ?: 0L,
                    subtotal = (row["subtotal"] as? Number)?.toLong(),
                    cash_given = (row["cash_tendered"] as? Number)?.toLong(),
                    cash_change = (row["cash_change"] as? Number)?.toLong(),
                    payment_method = row["payment_method"] as? String,
                    currency = row["currency"] as? String
                )
                
                val billMeta = com.example.myapplication.data.model.BillMeta(
                    needs_review = row["needs_review"] as? Boolean ?: false,
                    detect_confidence = (row["detect_confidence"] as? Number)?.toDouble() ?: 0.0,
                    processing_ms = (row["processing_time_ms"] as? Number)?.toDouble() ?: 0.0,
                    gemini_error = row["error_message"] as? String
                )
                
                val billResp = BillResponse(
                    bill_id = row["id"] as String,
                    status = row["status"] as String,
                    failed_step = row["failed_step"] as? String,
                    message = row["error_message"] as? String,
                    original_image_url = row["original_image_url"] as? String,
                    cropped_image_url = row["cropped_image_url"] as? String,
                    data = billData,
                    items = parsedItems,
                    meta = billMeta
                )
                
                Result.success(billResp)
            } else {
                Result.failure(Exception("Supabase Detail Error: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteBill(billId: String): Result<Boolean> {
        return try {
            val token = SupabaseManager.auth.currentAccessTokenOrNull() ?: supabaseKey
            val url = "$supabaseUrl/rest/v1/invoices"
            val response = supabaseApi.deleteBill(url, supabaseKey, "Bearer $token", "eq.$billId")
            
            if (response.isSuccessful) {
                Result.success(true)
            } else {
                Result.failure(Exception("Delete Failed: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
