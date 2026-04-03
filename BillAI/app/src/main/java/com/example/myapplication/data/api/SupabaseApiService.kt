package com.example.myapplication.data.api

import com.example.myapplication.data.model.BillSummary
import retrofit2.Response
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Query
import retrofit2.http.Url

interface SupabaseApiService {

    // Fetch from v_invoice_summary view
    @GET
    suspend fun listBills(
        @Url url: String,
        @Header("apikey") apiKey: String,
        @Header("Authorization") auth: String,
        @Query("user_id") userIdCondition: String, // format: eq.XYZ
        @Query("order") order: String = "created_at.desc"
    ): Response<List<BillSummary>>

    // Fetch from invoices table with related invoice_items
    @GET
    suspend fun getBillDetails(
        @Url url: String,
        @Header("apikey") apiKey: String,
        @Header("Authorization") auth: String,
        @Query("id") idCondition: String,
        @Query("select") select: String = "*,items:invoice_items(item_name,quantity,unit_price,total_price)"
    ): Response<List<Map<String, Any>>>

    // Delete from invoices table
    @DELETE
    suspend fun deleteBill(
        @Url url: String,
        @Header("apikey") apiKey: String,
        @Header("Authorization") auth: String,
        @Query("id") idCondition: String
    ): Response<Unit>
}
